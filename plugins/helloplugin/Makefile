# Copyright (c) 2026 Charlie Robinson
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
#
# Builds libHelloPlugin.so against the car's libraries. Run inside the car-matched GCC 4.7 toolchain image, which
# mounts this folder on /work and the dumped rootfs on /sysroot (read-only):
#
#   ../hmitest/build-plugin.sh . make
#
# (build the image once: docker build --platform linux/amd64 -t entrynav-tc ../hmitest)

# Unconditional, not ?=: make has a built-in default CXX=g++ that ?= would not override. A command-line
# CXX=... still wins over this.
CXX       = arm-linux-gnueabihf-g++-4.7
SYSROOT  ?= /sysroot
ARCH      = -march=armv7-a -mfpu=neon -mfloat-abi=hard
CXXFLAGS ?= -std=gnu++0x -O2 -Wall -Wextra $(ARCH)
PIC       = -fPIC -fvisibility=hidden -fvisibility-inlines-hidden

SRC = hello_app.cpp bmw_framework.cpp app_log.cpp app_guards.cpp car_log.cpp
OBJ = $(SRC:.cpp=.o)
DEP = $(OBJ:.o=.d)

# HU libraries: the HMI framework first, then the system libraries, with rpath-link so transitive deps resolve.
LIBDIRS   = -L$(SYSROOT)/opt/hmi/lib -L$(SYSROOT)/usr/lib -L$(SYSROOT)/lib -L$(SYSROOT)/usr/local/lib
RPATHLINK = -Wl,-rpath-link,$(SYSROOT)/opt/hmi/lib:$(SYSROOT)/usr/lib:$(SYSROOT)/lib:$(SYSROOT)/usr/local/lib
# --allow-shlib-undefined: the bmw::* symbols are left undefined here and resolved when HmiMain3D loads us.
LDSHLIB   = -Wl,--allow-shlib-undefined $(LIBDIRS) $(RPATHLINK)

.PHONY: all clean
all: libHelloPlugin.so

libHelloPlugin.so: $(OBJ)
	$(CXX) $(CXXFLAGS) $(PIC) -shared -Wl,-soname,libHelloPlugin.so $^ -o $@ \
	    $(LDSHLIB) -l:libAppFramework.A.so -l:libCoreFramework.A.so -lpthread -ldl

%.o: %.cpp
	$(CXX) $(CXXFLAGS) $(PIC) -MMD -MP -c $< -o $@

clean:
	rm -f $(OBJ) $(DEP) libHelloPlugin.so

-include $(DEP)
