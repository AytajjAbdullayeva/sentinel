// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// Changed: a reentrancy bug is deliberately introduced (state write moved AFTER the external call).
// Same contract name and same withdraw() signature as the baseline, so the finding's stable id is
// unchanged and the CI gate sees the SEVERITY of that path rise.
contract Vault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 bal = balances[msg.sender];
        require(bal > 0, "no balance");
        (bool ok, ) = msg.sender.call{value: bal}("");
        require(ok, "send failed");
        balances[msg.sender] = 0; // moved after the call -> reentrancy
    }
}
