// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// Baseline: safe withdraw (checks-effects-interactions).
contract Vault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 bal = balances[msg.sender];
        require(bal > 0, "no balance");
        balances[msg.sender] = 0;
        (bool ok, ) = msg.sender.call{value: bal}("");
        require(ok, "send failed");
    }
}
