// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// Oracle-manipulation pattern (Mango / bZx style): LendingPool.borrow trusts a spot price read
// from SpotOracle. Anyone can move that spot price by calling SpotOracle.swap, then borrow against
// the inflated collateral valuation and drain the pool.

interface IPriceOracle {
    function getPrice() external view returns (uint256);
}

contract SpotOracle is IPriceOracle {
    uint256 public reserveToken;
    uint256 public reserveQuote;

    function setReserves(uint256 t, uint256 q) external {
        reserveToken = t;
        reserveQuote = q;
    }

    // Permissionless swap that shifts the reserves, i.e. moves the reported spot price.
    function swap(uint256 quoteIn) external {
        reserveQuote += quoteIn;
        reserveToken -= quoteIn;
    }

    function getPrice() external view returns (uint256) {
        return (reserveQuote * 1e18) / reserveToken;
    }
}

contract LendingPool {
    IPriceOracle public oracle;
    mapping(address => uint256) public collateral;

    constructor(address o) {
        oracle = IPriceOracle(o);
    }

    function depositCollateral() external payable {
        collateral[msg.sender] += msg.value;
    }

    function borrow(uint256 amount) external {
        uint256 price = oracle.getPrice(); // trusts a manipulable spot price
        require((collateral[msg.sender] * price) / 1e18 >= amount, "undercollateralized");
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }
}
