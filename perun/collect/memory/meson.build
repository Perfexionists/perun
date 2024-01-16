perun_collect_memory_dir = perun_collect_dir / 'memory'

perun_collect_memory_c_files = files(
    'backtrace.c',
    'backtrace.h',
    'malloc.c',
)

# $(CC) -shared -fPIC malloc.c backtrace.c -o malloc.so -lunwind -ldl

shared_library(
    'malloc.so',
    perun_collect_memory_c_files,
    install: true,
    install_dir: py3.get_install_dir() / perun_collect_memory_dir,
    link_args: ['-lunwind', '-ldl'],
)

perun_collect_memory_files = files(
    '__init__.py',
    'filter.py',
    'parsing.py',
    'run.py',
    'syscalls.py',
)

py3.install_sources(
    perun_collect_memory_files,
    subdir: perun_collect_memory_dir,
)
