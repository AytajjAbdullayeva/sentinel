#!/usr/bin/env bash
# Fetch real open-source contracts at pinned commits into fixtures/external/.
set -euo pipefail
cd "$(dirname "$0")/../fixtures/external"

fetch() {  # name url commit
  if [ ! -d "$1/.git" ]; then git clone -q "$2" "$1"; fi
  git -C "$1" fetch -q --depth 1 origin "$3" 2>/dev/null || true
  git -C "$1" checkout -q "$3"
  echo "$1 @ $(git -C "$1" rev-parse HEAD)"
}

fetch oz    https://github.com/OpenZeppelin/openzeppelin-contracts.git 69c8def5f222ff96f2b5beff05dfba996368aa79  # v5.1.0
fetch univ2 https://github.com/Uniswap/v2-core.git                     6a9e7c97860676e0992f22a49665760444c1cdf5
fetch weth  https://github.com/gnosis/canonical-weth.git               0dd1ea3e295eef916d0c6223ec63141137d22d67
fetch safe  https://github.com/safe-global/safe-smart-account.git      bf943f80fec5ac647159d26161446ac5d716a294  # v1.4.1

# SWC Registry removed its labelled test cases from master; 3b6a6773 is the last commit that has them.
if [ ! -d swc/.git ]; then git clone -q https://github.com/SmartContractSecurity/SWC-registry.git swc; fi
if [ ! -d swc_cases/test_cases ]; then
  mkdir -p swc_cases
  git -C swc archive 3b6a6773592d07ca997df26dd63068d964f46d50 test_cases/solidity | tar -x -C swc_cases
fi
echo "swc_cases @ 3b6a6773592d07ca997df26dd63068d964f46d50"
