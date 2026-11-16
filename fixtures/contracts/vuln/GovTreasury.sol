// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// Governance-takeover pattern (Beanstalk style): the treasury's withdraw is guarded only by a
// governor check. Whoever becomes governor (e.g. via a captured governance proposal) can move all
// funds. The authority -> withdraw -> ETH topology is what makes the capture catastrophic.
contract GovTreasury {
    address public governor;

    constructor(address g) {
        governor = g;
    }

    modifier onlyGovernor() {
        require(msg.sender == governor, "not governor");
        _;
    }

    receive() external payable {}

    function setGovernor(address g) external onlyGovernor {
        governor = g;
    }

    function withdraw(address payable to, uint256 amount) external onlyGovernor {
        (bool ok, ) = to.call{value: amount}("");
        require(ok, "send failed");
    }
}
