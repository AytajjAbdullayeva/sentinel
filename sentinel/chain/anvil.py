"""Run a real Anvil node for the lifetime of a `with` block, and deploy real bytecode to it."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

from web3 import Web3

from sentinel.ingest.solc import ContractArtifact


def _anvil_binary() -> str:
    found = shutil.which("anvil") or str(Path.home() / ".foundry" / "bin" / "anvil")
    if not os.path.exists(found):
        raise FileNotFoundError("anvil not found; install Foundry (foundryup)")
    return found


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Anvil:
    def __init__(self, extra_args: list[str] | None = None, startup_timeout: float = 15.0):
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._args = [_anvil_binary(), "--port", str(self.port), "--silent", *(extra_args or [])]
        self._timeout = startup_timeout
        self._proc: subprocess.Popen | None = None
        self.w3: Web3 | None = None

    def __enter__(self) -> "Anvil":
        self._proc = subprocess.Popen(self._args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.w3 = Web3(Web3.HTTPProvider(self.url))
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(f"anvil exited: {self._proc.stderr.read().decode()}")
            try:
                if self.w3.is_connected():
                    return self
            except Exception:
                pass
            time.sleep(0.1)
        self.__exit__(None, None, None)
        raise TimeoutError("anvil did not become ready")

    def __exit__(self, *exc) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._proc.wait(timeout=10)


class DeploymentReverted(RuntimeError):
    pass


def deploy(w3: Web3, artifact: ContractArtifact, args: tuple = (), sender: str | None = None,
           value: int = 0) -> tuple[str, dict]:
    if not artifact.deployable:
        raise ValueError(f"{artifact.fqn} is not deployable ({artifact.kind}, abstract={artifact.abstract})")
    contract = w3.eth.contract(abi=artifact.abi, bytecode="0x" + artifact.bytecode)
    tx = contract.constructor(*args).transact({"from": sender or w3.eth.accounts[0], "value": value})
    receipt = w3.eth.wait_for_transaction_receipt(tx)
    if receipt["status"] != 1:
        raise DeploymentReverted(f"{artifact.fqn}: tx {tx.hex()} reverted")
    return receipt["contractAddress"], dict(receipt)
