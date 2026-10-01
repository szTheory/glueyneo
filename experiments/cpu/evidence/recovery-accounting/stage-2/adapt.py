"""MIT: explicit-context candidate transform; counts as adaptation support.

Run once on the six pristine files after the admission freeze. This recipe
retains upstream notices. Generated files are produced only by m68kmake.
"""
from pathlib import Path
import re
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
names = ("m68k.h", "m68kcpu.h", "m68kcpu.c", "m68kconf.h", "m68k_in.c", "m68kmake.c")
s = {n: (src / n).read_text() for n in names}
h, c, op = s["m68kcpu.h"], s["m68kcpu.c"], s["m68k_in.c"]
# Remove excluded closure edges without deleting later-model instruction text.
h = re.sub(r'^#include "softfloat/[^\n]+\n', '', h, flags=re.M)
h = re.sub(r'^\s*floatx80 fpr\[8\];[^\n]*\n', '', h, flags=re.M)
h = re.sub(r'\bint32\b', 'sint32', h)
c = re.sub(r'^extern (?:void m68040_fpu_op[01]|void m68881_mmu_ops|unsigned char m68ki_cycles|void \(\*m68ki_instruction_jump_table|void m68ki_build_opcode_table)[^\n]*\n', '', c, flags=re.M)
c = re.sub(r'^#include "m68k(?:fpu.c|mmu.h)"[^\n]*\n', '', c, flags=re.M)
op = re.sub(r'^extern void (?:m68040_fpu_op[01]|m68881_mmu_ops)[^\n]*\n', '', op, flags=re.M)
op = re.sub(r'\t\t(?:m68040_fpu_op[01]|m68881_mmu_ops)\(\);', '\t\tm68ki_exception_1111();', op)
op = op.replace('fprintf(stderr,"68040: unhandled PFLUSH\\n");', 'm68ki_exception_1111();')
# Dispatch is private derived storage. Immutable descriptor table stays shared.
for pattern in (r'^extern void \(\*m68ki_instruction_jump_table[^\n]*\n',
                r'^extern unsigned char m68ki_cycles[^\n]*\n',
                r'^void  \(\*m68ki_instruction_jump_table[^\n]*\n',
                r'^unsigned char m68ki_cycles\[NUM_CPU_TYPES\][^\n]*\n'):
    op = re.sub(pattern, '', op, flags=re.M)
op = op.replace('#define M68KOPS__HEADER', '#define M68KOPS__HEADER\n#include "m68k.h"')
op = op.replace('(*opcode_handler)(void)', '(*opcode_handler)(m68ki_context *)')
c = re.sub(r'\tstatic uint emulation_initialized = 0;.*?\n\t}\n', '\tm68ki_build_opcode_table();\n', c, count=1, flags=re.S)
# Remove singleton definitions and observational default-callback storage.
globals_ = {"m68ki_cpu": "cpu", "m68ki_initial_cycles": "initial_cycles",
 "m68ki_remaining_cycles": "remaining_cycles", "m68ki_tracing": "tracing",
 "m68ki_address_space": "address_space", "m68ki_aerr_address": "aerr_address",
 "m68ki_aerr_write_mode": "aerr_write_mode", "m68ki_aerr_fc": "aerr_fc",
 "m68ki_aerr_trap": "aerr_trap", "m68ki_bus_error_jmp_buf": "bus_error_trap",
 "m68ki_instruction_jump_table": "dispatch", "m68ki_cycles": "cycles"}
for name in globals_:
    c = re.sub(r'^\s*(?:int|uint|m68ki_cpu_core|sigjmp_buf|jmp_buf)\s+' + name + r'\b[^\n]*\n', '', c, flags=re.M)
    h = re.sub(r'^extern\s+(?:sint|uint|m68ki_cpu_core|sigjmp_buf|jmp_buf)\s+' + name + r'\b[^\n]*\n', '', h, flags=re.M)
c = re.sub(r'^static (?:unsigned )?int default_\w+_data;\n', '', c, flags=re.M)
c = re.sub(r'^(\s*)default_\w+_data = (\w+);', r'\1(void)\2;', c, flags=re.M)
# The BSD macro's extra argument is inconsistent with its upstream caller.
h = h.replace('m68ki_set_address_error_trap(m68k)', 'm68ki_set_address_error_trap()')
h = h.replace('m68ki_exception_address_error(m68k)', 'm68ki_exception_address_error()')
s.update({"m68kcpu.h":h, "m68kcpu.c":c, "m68k_in.c":op})
# Enumerate real function declarations, not function-like macros.
functions = set()
decl = re.compile(r'^(?P<prefix>(?:static inline |static |extern )?(?:(?:unsigned|signed) )?\w+[ \t*]+)(?P<name>(?:m68k\w*|default_\w+|OPER_\w+))\s*\(', re.M)
for n in ("m68k.h", "m68kcpu.h", "m68kcpu.c", "m68k_in.c"):
    functions.update(m.group('name') for m in decl.finditer(s[n]))
functions.discard('m68ki_trap_callback')  # conditional macro, not a real function
call = re.compile(r'\b(' + '|'.join(sorted(functions, key=len, reverse=True)) + r')\s*\(\s*(void\s*\)|\)|)')
for n in ("m68k.h", "m68kcpu.h", "m68kcpu.c", "m68k_in.c"):
    t = call.sub(lambda m: m[1] + '(ctx' + (')' if m[2] else ', '), s[n])
    t = decl.sub(lambda m: m[0], t)
    t = re.sub(r'(?m)^((?:static inline |static |extern )?(?:(?:unsigned|signed) )?\w+[ \t*]+(?:m68k\w*|default_\w+|OPER_\w+)\s*\()ctx', r'\1m68ki_context *ctx', t)
    # All stored callback signatures carry the same explicit context.
    t = re.sub(r'(\(\*(?:callback|\w+_callback)\)\()void\)', r'\1m68ki_context *)', t)
    t = re.sub(r'(\(\*(?:callback|\w+_callback)\)\()(?!m68ki_context)', r'\1m68ki_context *, ', t)
    t = re.sub(r'\b(CALLBACK_\w+)\((?!ctx)(\)?)', lambda m: m[1]+'(ctx'+(')' if m[2] else ', '), t)
    s[n] = t
# Forward declaration before all API and callback types.
s["m68k.h"] = s["m68k.h"].replace('#define M68K__HEADER', '#define M68K__HEADER\ntypedef struct m68ki_context m68ki_context;')
context = '''
/* Glueyneo: all execution mutation belongs to the explicitly passed instance. */
struct m68ki_context {
 m68ki_cpu_core cpu;
 int initial_cycles, remaining_cycles;
 uint tracing, address_space, aerr_address, aerr_write_mode, aerr_fc;
 jmp_buf aerr_trap, bus_error_trap, host_fault;
 void (*dispatch[0x10000])(m68ki_context *);
 unsigned char cycles[5][0x10000];
 void *bus_data;
 int (*bus_read)(void *, unsigned int, unsigned, unsigned int *);
 int (*bus_write)(void *, unsigned int, unsigned, unsigned int);
 unsigned long long instructions;
};
'''
context += ''.join('#define '+key+' (ctx->'+value+')\n' for key,value in globals_.items())
s["m68kcpu.h"] = s["m68kcpu.h"].replace('} m68ki_cpu_core;', '} m68ki_cpu_core;\n'+context)
s["m68kcpu.c"] = s["m68kcpu.c"].replace('m68ki_instruction_jump_table[REG_IR]();', 'm68ki_instruction_jump_table[REG_IR](ctx);\n\t\t\tctx->instructions++;')
s["m68kmake.c"] = s["m68kmake.c"].replace('static void %s(void)', 'static void %s(m68ki_context *ctx)')
s["m68kmake.c"] = s["m68kmake.c"].replace('OPER_%s_%d()', 'OPER_%s_%d(ctx)')
# Generated immediate operands are macros; accept the propagated argument too.
s['m68kcpu.h'] = re.sub(r'(#define OPER_I_\d+)\(\)', r'\1(ctx)', s['m68kcpu.h'])
# Put the complete upstream grant into both generated files via input sections.
notice = s['m68k_in.c'][s['m68k_in.c'].index('/* ======================================================================== */'):s['m68k_in.c'].index('/* Special thanks')]
for section in ('M68KMAKE_PROTOTYPE_HEADER', 'M68KMAKE_OPCODE_HANDLER_HEADER'):
    s['m68k_in.c'] = s['m68k_in.c'].replace(section+'\n', section+'\n'+notice, 1)
# Generator-generated EA expressions also invoke explicitly parameterized helpers.
for name in functions:
    s["m68kmake.c"] = re.sub(r'\b'+name+r'\(\)', name+'(ctx)', s["m68kmake.c"])
    s["m68kmake.c"] = re.sub(r'\b'+name+r'\((?!ctx)', name+'(ctx, ', s["m68kmake.c"])
for feature in ('010','EC020','020','030','040','PMMU'):
    s['m68kconf.h'] = re.sub(r'(#define M68K_EMULATE_'+feature+r'\s+)M68K_OPT_ON', r'\1M68K_OPT_OFF', s['m68kconf.h'])
for feature in ('PREFETCH','ADDRESS_ERROR','TRACE'):
    s['m68kconf.h'] = re.sub(r'(#define M68K_EMULATE_'+feature+r'\s+)M68K_OPT_OFF', r'\1M68K_OPT_ON', s['m68kconf.h'])
dst.mkdir(parents=True, exist_ok=True)
for name,text in s.items():
    (dst/name).write_text(text)
print(f"Adapted {len(names)} inputs; propagated {len(functions)} functions")
