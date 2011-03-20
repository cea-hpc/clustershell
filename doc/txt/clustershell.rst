ClusterShell is an event-based Python library to execute commands on local or
distant cluster nodes in parallel depending on the selected engine and worker
mechanisms. The library provides also advanced nodeset and node groups
handling methods. Its goal is to improve the administration of cluster by
providing a lightweight but scalable API for developers.

User tools
----------

ClusterShell also provides with the library three convenient Python command-line
programs:

- **clush**: issue commands to cluster nodes and format output

Example of use:

::

  $ clush -abL uname -r
  node[32-49,51-71,80,82-150,156-159]: 2.6.18-164.11.1.el5
  node[3-7,72-79]: 2.6.18-164.11.1.el5_lustre1.10.0.36
  node[2,151-155]: 2.6.31.6-145.fc11.2.x86_64

See *man clush* for more details.

- **clubak**: improved dshbak to gather and sort dsh-like outputs

See *man clubak* for more details.

- **nodeset**: compute advanced nodeset operations

Examples of use:

::

  $ echo node160 node161 node162 node163 | nodeset -f
  node[160-163]

  $ nodeset -f node[0-7,32-159] node[160-163]
  node[0-7,32-163]

  $ nodeset -e node[160-163]
  node160 node161 node162 node163

  $ nodeset -f node[32-159] -x node33
  node[32,34-159]

  $ nodeset -f node[32-159] -i node[0-7,20-21,32,156-159]
  node[32,156-159]

  $ nodeset -f node[33-159] --xor node[32-33,156-159]
  node[32,34-155]

  $ nodeset -l
  @oss
  @mds
  @io
  @compute

  $ nodeset -e @mds
  node6 node7

See *man nodeset* for more details.

Please visit the ClusterShell website_.

.. _website: http://clustershell.sourceforge.net

