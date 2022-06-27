# RETURN opcode

## Procedure

### EVM behavior

The `RETURN` opcode terminates the call, then:

1. If it's a root call, it ends the execution.
2. Otherwise,  and
   restores caller's context and switch to it.

1. If it's an `is_create` call context, it copies the specified memory chunk to
   the bytecode identified by the hash of such memory chunk
2. Otherwise, it copies the specified memory chunk to the callers memory

### Circuit behavior

The circuit first checks the `result` in call context is indeed success.  Then:

1. If it's a root call, it transitions to `EndTx`.
2. Otherwise, it restore caller's context by reading to `rw_table`, then does step state transition to it.

We define source memory chunk by the `RETURN` arguments `offset` and `length`.

1. If it's an `is_create` call context, it copies the source memory chunk to the bytecode identified by its hash, using a lookup to the copy circuit with the following parameters:
    - src_id: callee.call_id
    - src_type: Memory
    - src_addr: arg_offset,
    - src_addr_end: callee.memory_size
    - length: min(arg_length, call_context[ReturnDataLength, caller_id])
    - dst_id: caller.call_id
    - dst_type: Memory
    - dst_addr: call_context[ReturnDataOffset, caller_id]
    - rw_counter: callee.rw_counter
    - rwc_inc: 2 * length
2. Otherwise, it copies the source memory chunk to the callers memory defined by the `*CALL*` arguments `retOffset`, `retLength`, using a lookup to the copy circuit with the following parameters:
    - src_id: callee.call_id
    - src_type: Memory
    - src_addr: arg_offset,
    - src_addr_end: callee.memory_size
    - length: arg_length
    - dst_id: code_hash
    - dst_type: Bytecode
    - dst_addr: 0
    - rw_counter: callee.rw_counter
    - rwc_inc: length
