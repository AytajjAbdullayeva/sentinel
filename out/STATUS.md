# Sentinel — Verified Capability Status

Generated from real test results: pytest --junitxml (junit.xml), 112 passed
Totals: 112 passed, 0 failed, 0 skipped.

| Capability | Status | Passing tests |
|---|---|---|
| AI narrative (grounded claims, hallucination removed) | VERIFIED | 5 |
| Attack graph build (exploit topologies, provenance) | VERIFIED | 5 |
| Attack graph paths (Yen k-shortest vs networkx) | VERIFIED | 17 |
| Auth & multi-tenancy (JWT, RBAC, cross-tenant isolation) | VERIFIED | 14 |
| CLI + CI gate (stable ids, gate can fail) | VERIFIED | 5 |
| Ingestion primitives (keccak selectors, EIP slots, pragma resolution) | VERIFIED | 13 |
| Monitoring (drift only from real chain events) | VERIFIED | 4 |
| Real ingestion (solc compile, selectors vs solc, proxy detection) | VERIFIED | 8 |
| Reporting honesty (status from real results, marketing lint) | VERIFIED | 5 |
| Scoring end-to-end (ranking on real reconstructions) | VERIFIED | 2 |
| Scoring formula (sourced inputs, insufficient-data) | VERIFIED | 10 |
| Simulation (feasibility from real Anvil receipts) | VERIFIED | 3 |
| Static analysis (Slither facts with verbatim origin) | VERIFIED | 6 |
| Value & authority (two-origin values, storage holdings, on-chain authority) | VERIFIED | 15 |

## Evidence (passing test node ids)

### AI narrative (grounded claims, hallucination removed) — VERIFIED
- `test_ai_narrative::test_stub_client_is_returned_without_key_and_never_errors`
- `test_ai_narrative::test_key_without_real_client_raises_not_fakes`
- `test_ai_narrative::test_grounding_removes_unsupported_claims`
- `test_ai_narrative::test_generate_drops_injected_ungrounded_claim_from_output`
- `test_ai_narrative::test_every_claim_maps_to_a_real_evidence_id`

### Attack graph build (exploit topologies, provenance) — VERIFIED
- `test_graph_build::test_no_edge_lacks_provenance_ever`
- `test_graph_build::test_reentrancy_topology`
- `test_graph_build::test_oracle_manipulation_topology`
- `test_graph_build::test_governance_takeover_topology`
- `test_graph_build::test_topologies_are_distinct`

### Attack graph paths (Yen k-shortest vs networkx) — VERIFIED
- `test_graph_paths::test_add_edge_requires_provenance`
- `test_graph_paths::test_add_edge_requires_existing_endpoints`
- `test_graph_paths::test_duplicate_edge_merges_provenance`
- `test_graph_paths::test_shortest_path_simple`
- `test_graph_paths::test_yen_returns_distinct_ordered_paths`
- `test_graph_paths::test_yen_matches_networkx[0]`
- `test_graph_paths::test_yen_matches_networkx[1]`
- `test_graph_paths::test_yen_matches_networkx[2]`
- `test_graph_paths::test_yen_matches_networkx[3]`
- `test_graph_paths::test_yen_matches_networkx[4]`
- `test_graph_paths::test_yen_matches_networkx[5]`
- `test_graph_paths::test_yen_matches_networkx[6]`
- `test_graph_paths::test_yen_matches_networkx[7]`
- `test_graph_paths::test_yen_matches_networkx[8]`
- `test_graph_paths::test_yen_matches_networkx[9]`
- `test_graph_paths::test_yen_matches_networkx[10]`
- `test_graph_paths::test_yen_matches_networkx[11]`

### Auth & multi-tenancy (JWT, RBAC, cross-tenant isolation) — VERIFIED
- `test_api_auth::test_missing_token_is_401`
- `test_api_auth::test_malformed_token_is_401`
- `test_api_auth::test_wrong_signature_is_401`
- `test_api_auth::test_alg_none_token_is_401`
- `test_api_auth::test_expired_token_is_401`
- `test_api_auth::test_valid_token_allows_access`
- `test_api_auth::test_login_wrong_password_is_401`
- `test_api_auth::test_login_success_returns_scoped_token`
- `test_api_auth::test_viewer_cannot_create_scan`
- `test_api_auth::test_analyst_can_create_scan`
- `test_api_auth::test_cross_tenant_read_is_404_and_list_is_isolated`
- `test_api_auth::test_ws_without_token_is_rejected`
- `test_api_auth::test_ws_expired_token_is_rejected`
- `test_api_auth::test_ws_valid_token_streams_only_own_org`

### CLI + CI gate (stable ids, gate can fail) — VERIFIED
- `test_cli_gate::test_stable_id_is_identical_across_runs_and_versions`
- `test_cli_gate::test_gate_passes_on_no_change`
- `test_cli_gate::test_gate_fails_when_reentrancy_introduced`
- `test_cli_gate::test_baseline_is_below_threshold`
- `test_cli_gate::test_installed_binary_scan_and_gate`

### Ingestion primitives (keccak selectors, EIP slots, pragma resolution) — VERIFIED
- `test_primitives::test_keccak_is_not_nist_sha3`
- `test_primitives::test_known_selectors[transfer(address,uint256)-a9059cbb]`
- `test_primitives::test_known_selectors[approve(address,uint256)-095ea7b3]`
- `test_primitives::test_known_selectors[deposit()-d0e30db0]`
- `test_primitives::test_known_selectors[withdraw(uint256)-2e1a7d4d]`
- `test_primitives::test_tuple_signature_canonicalisation`
- `test_primitives::test_cross_check_rejects_mismatch`
- `test_primitives::test_eip_slot_constants`
- `test_primitives::test_pragma_resolution[pragma solidity =0.5.16;-0.5.16]`
- `test_primitives::test_pragma_resolution[pragma solidity >=0.4.22 <0.6;-0.5.17]`
- `test_primitives::test_pragma_resolution[pragma solidity ^0.8.20;-0.8.24]`
- `test_primitives::test_pragma_resolution[pragma solidity ^0.4.18;-0.4.26]`
- `test_primitives::test_pragma_intersection_across_files`

### Monitoring (drift only from real chain events) — VERIFIED
- `test_monitor::test_no_change_yields_no_drift`
- `test_monitor::test_real_upgrade_is_detected`
- `test_monitor::test_real_role_grant_is_detected`
- `test_monitor::test_poll_before_baseline_raises`

### Real ingestion (solc compile, selectors vs solc, proxy detection) — VERIFIED
- `test_ingest_real::test_struct_selector_matches_solc`
- `test_ingest_real::test_three_units_compile_with_expected_compilers`
- `test_ingest_real::test_function_counts_differ_by_structure`
- `test_ingest_real::test_every_function_is_located_in_source`
- `test_ingest_real::test_assets_are_unknown_not_empty`
- `test_ingest_real::test_non_proxies_are_not_proxies`
- `test_ingest_real::test_eip1967_uups_proxy_detected_and_tracks_upgrade`
- `test_ingest_real::test_beacon_proxy_detected`

### Reporting honesty (status from real results, marketing lint) — VERIFIED
- `test_report::test_parsing_counts_statuses`
- `test_report::test_verified_only_when_passing_and_no_failures`
- `test_report::test_report_lists_real_nodeids_only`
- `test_report::test_generated_report_has_no_marketing_language`
- `test_report::test_lint_catches_marketing`

### Scoring end-to-end (ranking on real reconstructions) — VERIFIED
- `test_scoring_pipeline::test_reentrancy_scored_higher_than_oracle_and_patched_infeasible`
- `test_scoring_pipeline::test_clean_contract_path_without_simulation_is_insufficient`

### Scoring formula (sourced inputs, insufficient-data) — VERIFIED
- `test_scoring::test_weights_must_sum_to_one`
- `test_scoring::test_feasible_path_is_scored_with_sourced_components`
- `test_scoring::test_infeasible_from_simulation_scores_zero_not_unknown`
- `test_scoring::test_missing_feasibility_is_insufficient_data`
- `test_scoring::test_static_only_feasibility_is_insufficient`
- `test_scoring::test_missing_price_is_insufficient_no_invented_value`
- `test_scoring::test_onchain_value_evidence_scores_higher_than_declared`
- `test_scoring::test_reentrancy_outranks_oracle_and_scores_differ`
- `test_scoring::test_score_changes_when_input_changes`
- `test_scoring::test_no_numeric_fallbacks_in_scoring_code`

### Simulation (feasibility from real Anvil receipts) — VERIFIED
- `test_sim::test_reentrancy_feasible_on_vulnerable_infeasible_on_fixed`
- `test_sim::test_oracle_feasible_on_vulnerable_infeasible_on_fixed`
- `test_sim::test_engine_reports_infeasible_when_no_profit`

### Static analysis (Slither facts with verbatim origin) — VERIFIED
- `test_static_slither::test_reentrancy_fact_has_verbatim_origin`
- `test_static_slither::test_fixed_version_drops_the_reentrancy_eth_fact`
- `test_static_slither::test_no_invented_confidence_anywhere`
- `test_static_slither::test_every_fact_has_a_source_location`
- `test_static_slither::test_structure_facts_reflect_the_code`
- `test_static_slither::test_different_contracts_give_different_facts`

### Value & authority (two-origin values, storage holdings, on-chain authority) — VERIFIED
- `test_value_authority::test_quantity_requires_a_source_and_decimal`
- `test_value_authority::test_unknown_renders_as_unknown`
- `test_value_authority::test_declared_always_shows_badge`
- `test_value_authority::test_derived_value_is_declared_if_any_input_is_declared`
- `test_value_authority::test_total_is_unknown_if_any_part_is_unknown`
- `test_value_authority::test_declarations_require_explicit_fields`
- `test_value_authority::test_no_numeric_fallbacks_in_value_or_authority_code`
- `test_value_authority::test_onchain_value_is_pinned_to_its_block`
- `test_value_authority::test_pair_tokens_are_discovered_from_storage_layout`
- `test_value_authority::test_declared_price_prices_only_the_declared_token`
- `test_value_authority::test_safe_threshold_is_read_from_state[3-2]`
- `test_value_authority::test_safe_threshold_is_read_from_state[5-3]`
- `test_value_authority::test_timelock_delay_and_roles_are_read_from_state[172800]`
- `test_value_authority::test_timelock_delay_and_roles_are_read_from_state[3600]`
- `test_value_authority::test_non_authority_contract_yields_no_authority_facts`
