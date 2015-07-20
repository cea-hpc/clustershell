Introduction
============

ClusterShell provides a light, unified and robust command execution Python
framework, well-suited to ease daily administrative tasks of nowadays Linux
clusters. Some of the most important benefits of using ClusterShell are:

* to provide an efficient, parallel and highly scalable command execution
  engine in Python,
* to provide an unified node groups syntax and external group access (see the
  NodeSet class),
* to significantly speed up initial cluster setup and daily administrative tasks
  when using tools like :ref:`clush-tool` and :ref:`nodeset-tool`.

Originally created by the HPC Linux system development team at CEA [#]_ HPC
center in France, ClusterShell is designed around medium and long term ideas
of sharing cluster administration development time, and this according to two
axes:

* sharing administrative applications between main components of the computing
  center: compute clusters, but also storage clusters and server farms (so
  they can use the same efficient framework for their administrative
  applications),
* sharing administration techniques across multiple generations of
  super-computing clusters (first of all, to avoid that every cluster
  administration application has to implement its own command execution layer,
  but also to encourage the adoption of event-based coding model in
  administration scripts).

Two available coding models make the library well-suited for simple scripts or
for complex applications as well. Also, the library is fully cluster-aware and
has primarily been made for executing remote shell commands in parallel and
gathering output results. But it now also provides the developer a set of
extra features for administrative applications, like file copy support or
time-based notifications (timers) which are discussed in this documentation.


.. [#] French Alternative Energies and Atomic Energy Commission, a leading
       technological research organization in Europe
