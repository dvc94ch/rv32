.equ CONSTANT, 0b01010101
.equ GPIO_BASE, 0x5000
.global _start

.section .text
_start:
    li x1, CONSTANT
    li x2, GPIO_BASE
    sw x1, 0(x2)
    j _start
