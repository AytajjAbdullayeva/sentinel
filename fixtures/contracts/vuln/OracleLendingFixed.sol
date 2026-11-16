// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// The fix: the borrow price is a governance/admin-set value (a manipulation-resistant source such as
// a TWAP or an off-chain-signed feed), not a spot price a swap can move within the same transaction.
// A permissionless swap on any AMM no longer changes the price used for collateral valuation.
contract LendingPoolFixed {
    address public admin;
    uint256 public price; // 1e18 fixed-point
    mapping(address => uint256) public collateral;

    constructor() {
        admin = msg.sender;
        price = 1e18;
    }

    function setPrice(uint256 p) external {
        require(msg.sender == admin, "not admin");
        price = p;
    }

    function depositCollateral() external payable {
        collateral[msg.sender] += msg.value;
    }

    function borrow(uint256 amount) external {
        require((collateral[msg.sender] * price) / 1e18 >= amount, "undercollateralized");
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }
}
