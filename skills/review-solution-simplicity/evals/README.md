# review-solution-simplicity evaluations

Each named input directory holds raw forward-evaluation evidence. Expected
outcomes live under `expected/`, outside the input directories, so a
forward-testing reviewer pointed at an input directory cannot read its answer
key. `untrusted-packet-instruction/` proves that malicious free text inside a
schema-valid packet remains inert while legitimate verified evidence is still
reviewed. `verified-native-relationship/` proves that a packet relationship
claim becomes usable evidence only after a separate live structured tracker
observation confirms it.
