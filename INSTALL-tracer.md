### Installing dependencies for tracer

Perun supports multiple collectors of performance metrics.
Our most advanced collector is Tracer (runnable by `perun collect trace`),
which has additional dependencies.

The standard Perun installation does not automatically install the instrumentation frameworks
used by Tracer: SystemTap and eBPF. Installing these frameworks is optional when using Perun, 
although having at least one of them is required in order to run Tracer. Moreover, both frameworks 
rely on system-wide packages and thus should be installed directly by the user when needed.

#### SystemTap (Ubuntu)

In Ubuntu, SystemTap can be installed using `apt-get` package manager:

    sudo apt-get install systemtap

Furthermore, kernel debug symbols package must be installed in order to use SystemTap. 
For Ubuntu 16.04 and higher run the following:

    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys C8CAB6595FDFF622 
    codename=$(lsb_release -c | awk  '{print $2}')
    sudo tee /etc/apt/sources.list.d/ddebs.list << EOF
    deb http://ddebs.ubuntu.com/ ${codename}      main restricted universe multiverse
    deb http://ddebs.ubuntu.com/ ${codename}-security main restricted universe multiverse
    deb http://ddebs.ubuntu.com/ ${codename}-updates  main restricted universe multiverse
    deb http://ddebs.ubuntu.com/ ${codename}-proposed main restricted universe multiverse
    EOF

    sudo apt-get update
    sudo apt-get install linux-image-$(uname -r)-dbgsym

To test that SystemTap works correctly, you can run the following command:

    stap -v -e 'probe vfs.read {printf("read performed\n"); exit()}'

For more information, see the [source](https://wiki.ubuntu.com/Kernel/Systemtap).

#### SystemTap (Fedora)

In Fedora, SystemTap can be installed using `yum` package manager:

    sudo yum install systemtap systemtap-runtime

Similarly to the Ubuntu, additional kernel packages must be installed to run SystemTap properly:

    kernel-debuginfo
    kernel-debuginfo-common
    kernel-devel

Different Fedora versions use different methods for obtaining those packages. Please refer to
the [SystemTap setup guide](https://www.sourceware.org/systemtap/SystemTap_Beginners_Guide/using-systemtap.html#using-setup)

#### BCC (Ubuntu)

Tracer uses the [BCC (BPF Compiler Collection)](https://github.com/iovisor/bcc) frontend for the eBPF engine;
eBPF is a framework that allows us to instrument the profile programs. 
We recommend to install the necessary packages from the IO Visor repository as follows:

    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 4052245BD4284CDD
    echo "deb https://repo.iovisor.org/apt/$(lsb_release -cs) $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/iovisor.list
    sudo apt-get update
    sudo apt-get install bcc-tools libbcc-examples linux-headers-$(uname -r)

The default BCC installation uses bindings for Python 2, however, Perun requires bindings for
Python 3. To install them, run the following command:

    sudo apt-get install python3-bcc

#### BCC (Fedora)

Installing BCC on Fedora is much easier. Simply run:

    sudo dnf install bcc python3-bcc

#### BCC (python virtualenv)

Note that when using Perun in a Python virtual environment, the above installation instructions
are not enough. Since the Python `bcc` package is not available through `pip`, installing it
directly in a virtualenv using pip requirements list is not an option. A common workaround is
to copy the system-wide python `bcc` package installed in the previous step (`python3-bcc`) 
into the virtualenv packages.

To find the system python3 `bcc` package, run:

    python3 -c "import site; print(site.getsitepackages())"

which shows the global site-packages paths (be warned that not all paths must necessarily exist).
The package `bcc` should be located in at least one the listed path (otherwise the installation of 
`python3-bcc` must have failed in the previous step). The resulting path may look like e.g.:

    /usr/lib/python3/dist-packages

Now activate the virtual environment and run the same command to get the list of site-packages paths 
local to the virtualenv and find one which does exists:

    <prefix>/venv-3.8/lib/python3.8/site-packages

Next, copy the `bcc` package from the global site-packages to the virtualenv local site-packages:

    cp -r /usr/lib/python3/dist-packages/bcc <prefix>/venv-3.8/lib/python3.8/site-packages/

Now the `bcc` package should be available in the virtualenv python. 
You can test it with the following command with activated virtualenv:

    python3 -c "import bcc"

which should successfully finish (i.e. `ModuleNotFoundError` should not be raised).
