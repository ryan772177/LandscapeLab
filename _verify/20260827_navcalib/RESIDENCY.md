# Navmesh residency and memory, measured 2026-08-27

Owed before the region had 49 tiles' worth of navmesh to stream, not after.
Machine: 31.43 GB RAM, commit limit 223.43 GB.

## What is on disk

    nav chunk actor packages   64
    total                      756.6 MB
    median                     11.6 MB
    largest                    15.7 MB
    chunk grid                 102400 cm (1024 m) per chunk actor

## The editor holding EVERYTHING — the worst case this process can produce

Every World Partition region forced resident, all 64 nav chunk actors loaded,
all 219,659 foliage instances, 256 landscape proxies, the town's 1,142 volumes.

    editor working set     14.65 GB
    editor private bytes   20.63 GB
    system RAM free         6.12 GB of 31.43
    system commit used     37.01 GB of 223.43

**It fits, with 6.1 GB of physical headroom.** That is the question this
measurement existed to answer.

## What this is NOT

**This is an EDITOR figure with everything forced resident.** It is an UPPER
BOUND on the machine's ability to hold the world, not a shipping number:

- a cooked build streams differently and would need its own reading;
- the delta is not navmesh alone — forcing regions resident also loads
  landscape proxies, foliage and city actors, so no line here attributes memory
  to the navmesh specifically;
- **no PIE measurement was taken.** Unit 10's acceptance — nav resident before
  the streaming marker, at mounted speed — is still owed and is now testable,
  which it was not while the navmesh stopped 500 m from the spawn.

## The runtime expectation, stated as arithmetic and not as a measurement

Nav chunk actors stream with World Partition at 1024 m per chunk. A streaming
radius of R chunks holds `(2R+1)^2` of them:

    R = 1     9 chunks    ~104 MB
    R = 2    25 chunks    ~290 MB
    R = 3    49 chunks    ~568 MB

**Computed from the median chunk size, not observed.** The real figure depends
on the runtime streaming range, which nobody here has set deliberately.

## The API that does not exist

`SystemLibrary.get_platform_memory_stats` is NOT in the 5.8 reflected surface —
the payload reported `UNREADABLE` with the exception text rather than a number,
and the generated Python stub carries no memory-statistics function at all.
An API remembered is an API guessed (non-negotiable 23).

Measuring the process from the OS is a better instrument anyway: it is a
DIFFERENT REPRESENTATION from anything the editor would report about itself.
