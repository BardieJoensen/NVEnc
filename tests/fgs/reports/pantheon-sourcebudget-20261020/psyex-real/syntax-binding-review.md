# R15 dynamic syntax-binding result

Executed the frozen binder SHA `34689de8b365801e762fd80a83ec9a349d88bb944c667e96da7bab9edce9323d` under `nice10/taskset8-11` against completed encoder receipt SHA `8234fcf3c6c8d69522646d6e4b34973639dcdbce30696f4bb0474b583630996a`. It exited zero; stderr is empty. Result SHA is `f4767eb474745c2722d16099d519db9b787b65b5d013dff713956ccad66e05ea`; event population SHA `ba2feb9d…`; trace-headers log SHA `0bbbc759…`.

The independent lifecycle contains 336 packets/displays, 502 frame headers, 336 coded events, 166 show-existing events, and exactly one display action per packet. Display216 is show-existing event325 through slot4. It resolves, without an intervening slot4 refresh, to hidden coded event314 / coded ordinal210: frame type1, showable1, order hint88, normalized refresh16. The exact type-6 frame OBU starts at IVF file offset225117553, is1,045,192 bytes, and has SHA `b23d36fa4f00c81ff8d581ddbaf0ee8613f258cdadd1c6472bef1c7a0c169ea2`.

Thus the new stream independently reproduces every immutable target/population guard compiled into the existing R10 observer. Reuse is admitted at the mapping stage; decoder/replay neutrality and complete trace admission remain separately required.
