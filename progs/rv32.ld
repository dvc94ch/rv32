MEMORY
{
    ROM : ORIGIN = 0x80000000, LENGTH = 1024
    RAM : ORIGIN =     0x4000, LENGTH = 0x1000
}

SECTIONS
{
    .text :
    {
        *(.text .text.*);
    } > ROM

    .data : ALIGN(4)
    {
        *(.data .data.*);
    } > RAM
}
