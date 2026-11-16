// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// Reentrancy pattern (TheDAO / SWC-107): the external call to msg.sender happens BEFORE the
// balance is zeroed, so a malicious receiver can re-enter withdraw() and drain the vault.
contract ReentrantVault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 bal = balances[msg.sender];
        require(bal > 0, "no balance");
        (bool ok, ) = msg.sender.call{value: bal}(""); // external call before state update
        require(ok, "send failed");
        balances[msg.sender] = 0; // state write after the call -> reentrancy
    }
}
