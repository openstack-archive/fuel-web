.. _custom-bootstrap-node:


Bootstrap node
==============

You can modify the bootstrap node in two different ways:

* add the required driver into bootstrap

* create a custom bootstrap to replace the default one


Let's take a look at the first approach in more details.

Injecting the required driver during Fuel ISO installation
----------------------------------------------------------

Great number of proprietary drivers for equipment cannot be shipped with
GA Fuel ISO due to legal issues and should be installed by users themselves.

This document describes the steps to adding (injecting)
required drivers during Fuel ISO
installation procedure.

Injection workflow consists of several stages:

#. Prepare the disk driver image with the required kernel modules (for CentOs and Ubuntu)
#. Add drivers when deploying the Fuel Master node (CentOS)
#. Modify bootstrap (CentOS)
#. Modify CentOs
#. Modify Images from Image Base Provision (Ubuntu CentOs)


Prepare disk driver image for CentOS
++++++++++++++++++++++++++++++++++++

The disk driver image should have the following structure:

::


    /
    |.rundepmod - The (empty) trigger file must be present to start depmod
    |rhdd3   - DD marker, contains the DD's description string
    /lib/modules/<kernel-version>/kernel/<path-to-the-driver>/<module.ko>
    /rpms
    |  /x86_64 - contains RPMs for this arch and acts as Yum repo

The easiest way is to create a squashfs image.
Let's put all required files into the folder called *squashfs-src* and create the image.
For example, we need the 2.6.32-504 (CentOs 6.6) kernel:

#. Create the working folder dd-src:

   ::

       mkdir dd-src

#. Create auxiliary files:

   ::

      touch ./dd-src/.rundepmod
      echo "CentOs driver disk" > ./dd-src/rhdd3

#. Put the kernel modules into:

   ::

       mkdir ./dd-src/lib
       mkdir ./dd-src/lib/modules
       mkdir ./dd-src/lib/modules/2.6.32-504.1.3.el6.x86_64
       mkdir ./dd-src/lib/modules/2.6.32-504.1.3.el6.x86_64/kernel
       mkdir ./dd-src/lib/modules/2.6.32-504.1.3.el6.x86_64/kernel/drivers
       mkdir ./dd-src/lib/modules/2.6.32-504.1.3.el6.x86_64/kernel/drivers/scsi
       cp hpvsa.ko ./dd-src/lib/modules/2.6.32-504.1.3.el6.x86_64/kernel/drivers/scsi

#. Put the RPMs:

   ::

        mkdir ./dd-src/rpms
        mkdir ./dd-src/rpms/x86_64
        cp kmod-hpvsa-1.2.10-120.rhel7u0.x86_64.rpm  kmod-hpvsa-1.2.12-110.rhel6u6.x86_64.rpm ./dd-src/rpms/x86_64 
        createrepo -pv ./dd-src/rpms/x86_64/

#. Create the squashfs image (centos-hpvsa-dd.img):

   ::

      mksquashfs dd-src/ centos-hpvsa-dd.img


You can also create an alternative dd (non-squashfs) image
with running the following commands:

#. Create an empty image:

   ::

       dd if=/dev/zero of=centos-hpvsa-rhdd3.img bs=1k count=6144

#. Format it:

   ::

       mkfs ext3 -L OEMDRV -F centos-hpvsa-rhdd3.img

#. Mount and copy files and umount the image:

   ::

       mkdir -p /mnt/dd-img
       mount -o loop,rw,sync centos-hpvsa-rhdd3.img /mnt/dd-img
       cp -R ./squashfs-src/ /mnt/dd-img
       umount /mnt/dd-img


Modifying bootstrap
+++++++++++++++++++

.. note:: Currently, the bootstrap is based on CentOS (kernel and modules).


Let's assume that the Fuel Master node has been deployed:

#. Connect to the Fuel master node:

   ::

       ssh root@<your-Fuel-Master-node-IP>

#. Repack the CentOS disk driver:

   ::

      mount -o loop -t <your-image-fs-type> centos-hpvsa-dd.img  /mnt/dd-img
      find /mnt/dd-img | cpio --quiet -o -H newc | gzip -9 > /tmp/initrd_update.img

#. Copy into the TFTP (PXE) bootstrap folder:

   ::

       cp /tmp/initrd_update.img /var/www/nailgun/bootstrap/
       chmod 755 /var/www/nailgun/bootstrap/initrd_update.img

#. Copy inside the cobbler container to the folder:
   
   ::

       dockerctl copy initrd_update.img cobbler:/var/lib/tftpboot/initrd_update.img

#. Modify the bootstrap menu initrd parameter.

#. Log into the cobbler container:

  ::

     dockerctl shell cobbler

#. Get the variable kopts variable value:

   ::

        cobbler profile dumpvars --name=bootstrap | grep kernel_options
        kernel_options : ksdevice=bootif locale=en_US text mco_user=mcollective initrd=initrd_update.img biosdevname=0 lang url=http://10.20.0.2:8000/api priority=critical mco_pass=HfQqE2Td kssendmac

#. Add *initrd=initrd_update.img* at the beginning of the string and re-sync the container.
   It turns into the kernel parameter passing to the kernel on boot
   'initrd=initramfs.img,initrd_update.img':

   ::

      cobbler profile edit --name bootstrap --kopts='initrd=initrd_update.img ksdevice=bootif lang=  locale=en_US text mco_user=mcollective priority=critical url=http://10.20.0.2:8000/api biosdevname=0 mco_pass=HfQqE2Td kssendmac'
      cobbler sync

#. Log into the Fuel Master node. Create the /tmp/initrd_update folder and re-pack the CentOS disk driver image.


Creating a custom bootstrap node
--------------------------------


Replacing default bootstrap node with the custom one
----------------------------------------------------

