from typing import Dict, Iterator, List, NewType, Optional, Sequence, Union, Mapping, Tuple

from .util import FQ, Expression, ConstraintSystem, cast_expr, MAX_N_BYTES, N_BYTES_MEMORY_ADDRESS
from .evm import (
    Tables,
    CopyDataTypeTag,
    CopyCircuitRow,
    RW,
    RWTableTag,
    FixedTableTag,
    CopyCircuit,
    TxContextFieldTag,
    BytecodeFieldTag,
    TxLogFieldTag,
)


def lt(lhs: Expression, rhs: Expression, n_bytes: int) -> FQ:
    assert n_bytes <= MAX_N_BYTES, "Too many bytes to composite an integer in field"
    assert lhs.expr().n < 256**n_bytes, f"lhs {lhs} exceeds the range of {n_bytes} bytes"
    assert rhs.expr().n < 256**n_bytes, f"rhs {rhs} exceeds the range of {n_bytes} bytes"
    return FQ(lhs.expr().n < rhs.expr().n)


def verify_row(cs: ConstraintSystem, rows: Sequence[CopyCircuitRow]):
    cs.constrain_bool(rows[0].q_step)
    cs.constrain_bool(rows[0].q_first)
    cs.constrain_bool(rows[0].q_last)
    cs.constrain_equal(rows[0].is_memory, cs.is_zero(rows[0].tag - CopyDataTypeTag.Memory))
    cs.constrain_equal(rows[0].is_bytecode, cs.is_zero(rows[0].tag - CopyDataTypeTag.Bytecode))
    cs.constrain_equal(rows[0].is_tx_calldata, cs.is_zero(rows[0].tag - CopyDataTypeTag.TxCalldata))
    cs.constrain_equal(rows[0].is_tx_log, cs.is_zero(rows[0].tag - CopyDataTypeTag.TxLog))

    is_last_two_rows = rows[0].q_last + rows[1].q_last
    with cs.condition(1 - is_last_two_rows) as cs:
        # not last two rows
        cs.constrain_equal(rows[0].id, rows[2].id)
        cs.constrain_equal(rows[0].log_id, rows[2].log_id)
        cs.constrain_equal(rows[0].tag, rows[2].tag)
        cs.constrain_equal(rows[0].addr + 1, rows[2].addr)
        cs.constrain_equal(rows[0].addr_end, rows[2].addr_end)

    with cs.condition(1 - rows[0].q_last) as cs:
        # not last row
        rw_diff = (1 - rows[0].is_pad) * (rows[0].is_memory + rows[0].is_tx_log)
        cs.constrain_equal(rows[0].rw_counter + rw_diff, rows[1].rw_counter)
        cs.constrain_equal(rows[0].rwc_inc_left - rw_diff, rows[1].rwc_inc_left)

    with cs.condition(rows[0].q_last) as cs:
        # rwc_inc_left == 1 for last row in the copy slot
        cs.constrain_zero(rows[0].rwc_inc_left - 1)


def verify_step(cs: ConstraintSystem, rows: Sequence[CopyCircuitRow], tables: Tables):
    with cs.condition(rows[0].q_step):
        # lookup to copy pairs
        tables.fixed_lookup(FQ(FixedTableTag.CopyPairs), rows[0].tag, rows[1].tag)
        # bytes_left == 1 for last step
        cs.constrain_zero(rows[1].q_last * (1 - rows[0].bytes_left))
        # bytes_left == bytes_left_next + 1 for non-last step
        cs.constrain_zero((1 - rows[1].q_last) * (rows[0].bytes_left - rows[2].bytes_left - 1))
        # write value == read value
        cs.constrain_equal(rows[0].value, rows[1].value)
        # value == 0 when is_pad == 1 for read
        cs.constrain_zero(rows[0].is_pad * rows[0].value)
        # is_pad == 1 - (src_addr < src_addr_end) for read row
        cs.constrain_equal(
            1 - lt(rows[0].addr, rows[0].addr_end, N_BYTES_MEMORY_ADDRESS), rows[0].is_pad
        )
        # is_pad == 0 for write row
        cs.constrain_zero(rows[1].is_pad)


def verify_copy_table(copy_circuit: CopyCircuit, tables: Tables):
    cs = ConstraintSystem()
    copy_table = copy_circuit.table()
    n = len(copy_table)
    for i, row in enumerate(copy_table):
        rows = [
            row,
            copy_table[(i + 1) % n],
            copy_table[(i + 2) % n],
        ]
        # constrain on each row and step
        verify_row(cs, rows)
        verify_step(cs, rows, tables)

        # lookup into tables
        if row.is_memory == 1 and row.is_pad == 0:
            val = tables.rw_lookup(
                row.rw_counter, 1 - row.q_step, FQ(RWTableTag.Memory), row.id, row.addr
            ).value
            cs.constrain_equal(cast_expr(val, FQ), row.value)
        if row.is_bytecode == 1 and row.is_pad == 0:
            val = tables.bytecode_lookup(
                row.id, FQ(BytecodeFieldTag.Byte), row.addr, row.is_code
            ).value
            cs.constrain_equal(cast_expr(val, FQ), row.value)
        if row.is_tx_calldata == 1 and row.is_pad == 0:
            val = tables.tx_lookup(row.id, FQ(TxContextFieldTag.CallData), row.addr).value
            cs.constrain_equal(val, row.value)
        if row.is_tx_log == 1:
            val = tables.rw_lookup(
                row.rw_counter,
                FQ(RW.Write),
                FQ(RWTableTag.TxLog),
                row.id,
                row.log_id,
                FQ(TxLogFieldTag.Data),
                row.addr,
            ).value
            cs.constrain_equal(cast_expr(val, FQ), row.value)
