# Qubla
www.absimp.org/qubla

## Introduction

Qubla is a language framework for defining quantum logics in a very similar
manner as it is usually done for classical algorithms. In Qubla, arbitrary
boolean functions could be defined, independently of whether the input bits are
classical or quantum ones. Additionally, these functions could be applied on
any mixture of classical or qubits, all additional housekeeping chores
(precalculation of the fully classical expressions, enforcing unitarity of
quantum transformations) are done automatically provided. The output of the
compiler is a quantum logic as a chain of unitary transformations. A 3rd party
application or a custom script should be employed to run this quantum logic
on a simulator or turn it into a runnable artifact for real quantum hardware.
For testing purposes, a simple state vector simulator is provided.

The Qubla compiler is written entirely in Python language and provided as a
library, so no command line executable or any other UI is available at the
moment.

## Installation

Download the source code from https://github.com/ggalfi/qubla. Add the `pypkg`
directory to Python's library path, and then Qubla could be imported.

## Usage

See the Jupyter notebooks in `examples` directory.



