perun_collect_memory_dir = perun_collect_dir / 'memory'

perun_collect_memory_c_files = files(
    'backtrace.c',
    'backtrace.h',
    'malloc.c',
)

# $(CC) -shared -fPIC malloc.c backtrace.c -o malloc.so -lunwind -ldl

config_h = configuration_data()
c = meson.get_compiler('c')
# Check for link.h header, skip compilation if it's missing.
link_h = c.has_header('link.h', required: false)
if link_h
    # Check for libunwind
    libunwind_dep = dependency('libunwind', required: false)
    libunwind_h = c.find_library('unwind', required: false, dirs: ['/usr/lib', '/usr/local/lib'])

    if libunwind_dep.found() and libunwind_h.found()
        config_h.set('HAVE_LIBUNWIND', 1)
        link_args = ['-lunwind', '-ldl']
    else
        config_h.set('HAVE_LIBUNWIND', 0)
        link_args = ['-ldl']
    endif

    shared_library(
        'malloc.so',
        perun_collect_memory_c_files,
        install: true,
        install_dir: py3.get_install_dir() / perun_collect_memory_dir,
        link_args: link_args,
    )
endif

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
