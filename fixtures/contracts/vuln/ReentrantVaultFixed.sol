// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// The fix: checks-effects-interactions. The balance is zeroed BEFORE the external call, so a
// re-entrant withdraw sees a zero balance and reverts.
contract ReentrantVaultFixed {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 bal = balances[msg.sender];
        require(bal > 0, "no balance");
        balances[msg.sender] = 0; // effects before interaction
        (bool ok, ) = msg.sender.call{value: bal}("");
        require(ok, "send failed");
    }
}
