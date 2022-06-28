# RETURN opcode

## Procedure

### EVM behavior

The `RETURN` opcode terminates the call, and:

1. If it's an `is_create` call context, it returns the specified memory chunk
   as deployment code identified by the hash of such memory chunk.
2. Otherwise if it's not a root call, it returns the specified memory chunk to
   the caller.

1. If it's a root call, it ends the execution.
2. Otherwise restores caller's context and switch to it.

### Circuit behavior

The circuit first checks the `result` in call context is indeed success.  Then:

We define source memory chunk by the `RETURN` arguments `return_offset` and `return_length`.

Perform memory expansion to `return_offset + return_length`.

1. If it's an `is_create` call context, it copies the source memory chunk to the bytecode identified by its hash, using a lookup to the copy circuit with the following parameters:
    - src_id: callee.call_id
    - src_type: Memory
    - src_addr: return_offset,
    - src_addr_end: return_offset + return_length
    - length: return_length
    - dst_id: code_hash
    - dst_type: Bytecode
    - dst_addr: 0
    - rw_counter: callee.rw_counter
    - rwc_inc: length
2. Otherwise, if it's not a root call, it copies the source memory chunk to the callers memory defined by the `*CALL*` arguments `retOffset`, `retLength`, using a lookup to the copy circuit with the following parameters:
    - src_id: callee.call_id
    - src_type: Memory
    - src_addr: return_offset,
    - src_addr_end: min(return_offset + return_length, callee.memory_size)
    - length: min(return_length, call_context[ReturnDataLength, callee_id])
    - dst_id: caller.call_id
    - dst_type: Memory
    - dst_addr: call_context[ReturnDataOffset, callee_id]
    - rw_counter: callee.rw_counter
    - rwc_inc: 2 * length

1. If it's a root call, it transitions to `EndTx`.
2. Otherwise, it restore caller's context by reading to `rw_table`, then does step state transition to it.


### Gas cost

The only gas cost incurred by `RETURN` is the one that comes from the memory
expansion related to the returned memory chunk.

## Code

Please refer to `src/zkevm_specs/evm/execution/return.py`.
