.equ CONSTANT, 0xdeadbeef
.global _start

.section .data
var1:
    .word 0x00000000

.section .text
_start:
    li x1, CONSTANT
    sw x1, var1, x3
    lw x2, var1
    beq x2, x1, pass
    ecall
pass:
    addi x0, x0, 0
