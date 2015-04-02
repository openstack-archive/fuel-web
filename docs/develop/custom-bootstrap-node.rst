.. _custom-bootstrap-node:


Bootstrap node
==============

When you would like to bring changes
into bootstrap, you should take up either of the
options:

* create an additional
  "piece" of bootstrap (initrd_update)
  that will be injected into the
  original initramfs image on the bootstrap.
  That means, avoid modifying the original initramfs
  image for bootstrap

* modify the original initramfs image manually

* create a custom initramfs image for
  bootstrap to replace the default one.

Let's take a look at every approach in more details.

Creating and injecting the initrd_update into bootstrap
-------------------------------------------------------

A typical use case for creating initrd_update looks as follows:
a great number of proprietary drivers for equipment cannot be
shipped with GA Fuel ISO due to legal issues
and should be installed by users themselves.

That means, you can add (or inject) the required issues (drivers,
scripts etc.) during Fuel ISO
installation procedure.

Injection workflow consists of several stages:

#. Prepare the injected initramfs image with the required kernel modules (for CentOS).
#. Modify bootstrap (CentOS)

Prepare injected initramfs image for CentOS
+++++++++++++++++++++++++++++++++++++++++++

The injected initramfs image should contain
the files what are going to be put on (or let's say injected into)
the original initramfs on the bootstrap in addition to
the deployed (original) RAM file system.

The injected initramfs image should have the following structure:

::

    /
    /lib/modules/<kernel-version>/kernel/<path-to-the-driver>/<module.ko>
    /etc/modprobe.d/<module>.conf

Let's put all required files into the folder called *dd-src* and create the image.
For example, we need the 2.6.32-504 (CentOs 6.6) kernel:

#. Create the working folder dd-src:

   ::

       mkdir dd-src

#. Put the kernel modules into:

   ::

      mkdir -p ./dd-src/lib/modules/2.6.32-504.1.3.el6.x86_64/kernel/drivers/scsi
      cp hpvsa.ko ./dd-src/lib/modules/2.6.32-504.1.3.el6.x86_64/kernel/drivers/scsi


#. Put the *<module-name>.conf* file with the modprobe command into
   the *etc/modprobe.d/* folder:

   ::

      mkdir -p ./dd-src/etc/modprobe.d/
      echo modprobe hpvsa > ./dd-src/etc/modprobe.d/hpvsa.conf
      chmod +x ./dd-src/etc/modprobe.d/hpvsa.conf


   There is the second (deprecated) way:
   create the */etc/rc.modules* executable file and list the command to probe with the module name.
   Do not use */etc/rc.local* file for this purpose,
   because it is too late for init hardware:

   ::

      mkdir ./dd-src/etc
      echo modprobe hpvsa > ./dd-src/etc/rc.modules
      chmod +x ./dd-src/etc/rc.modules




#. Create the dd-src.tar.gz file for coping to the Fuel Master node:

   ::

      tar -czvf dd-src.tar.gz ./dd-src

   The *dd-src.tar.gz* file can now be copied to the Fuel Master node.


Adding initrd_update image to the bootstrap
+++++++++++++++++++++++++++++++++++++++++++

.. note:: Currently, the bootstrap is based on CentOS (kernel and modules).


Let's assume that the Fuel Master node has been deployed:

#. Connect to the Fuel Master node:

   ::

       ssh root@<your-Fuel-Master-node-IP>

#. Prepare initramfs update image:

   ::

      tar -xzvf dd-src.tar.gz
      find dd-src/ | cpio --quiet -o -H newc | gzip -9 > /tmp/initrd_update.img

#. Copy into the TFTP (PXE) bootstrap folder:

   ::

       cp /tmp/initrd_update.img /var/www/nailgun/bootstrap/
       chmod 755 /var/www/nailgun/bootstrap/initrd_update.img

#. Copy inside the cobbler container to the folder:

   ::

       dockerctl copy initrd_update.img cobbler:/var/lib/tftpboot/initrd_update.img

#. Modify the bootstrap menu initrd parameter.

   * Log into the cobbler container:

     ::

         dockerctl shell cobbler

   * Get the variable kopts variable value:

      ::

          cobbler profile dumpvars --name=bootstrap | grep kernel_options
          kernel_options : ksdevice=bootif locale=en_US text mco_user=mcollective initrd=initrd_update.img biosdevname=0 lang url=http://10.20.0.2:8000/api priority=critical mco_pass=HfQqE2Td kssendmac

   * Add *initrd=initrd_update.img* at the beginning of the string
     and re-sync the container. It turns into the kernel
     parameter passing to the kernel on boot
     'initrd=initramfs.img,initrd_update.img':

     ::

         cobbler profile edit --name bootstrap --kopts='initrd=initrd_update.img ksdevice=bootif lang=  locale=en_US text mco_user=mcollective priority=critical url=http://10.20.0.2:8000/api biosdevname=0 mco_pass=HfQqE2Td kssendmac'
         cobbler sync


Modifying initramfs image manually for bootstrap node
-----------------------------------------------------

To edit the initramfs (initrd) image,
you should unpack it, modify and pack back.
Initramfs image is a gzip-ed cpio archive.

To change initramfs image, follow these steps:

#. Create a folder for modifying initramfs image and copy the initramfs image into it:

   ::

     mkdir /tmp/initrd-orig
     dockerctl copy cobbler:/var/lib/tftpboot/images/bootstrap/initramfs.img /tmp/initrd-orig/

#. Unpack initramfs image. First of all, unzip it:

   ::

      cd /tmp/initrd-orig/
      mv initramfs.img initramfs.img.gz
      gunzip initramfs.img.gz

#. Unpack the cpio archive to the initramfs folder:

   ::

      mkdir initramfs
      cd initramfs
      cpio -i < ../initramfs.img

#. Now you have the file system what you have in the RAM on the bootstrap:

   ::

     ls -l /tmp/initrd-orig/initramfs

#. Modify it as you need. For example, copy files or modify the scripts:

   ::

      cp hpvsa.ko lib/modules/2.6.32-504.1.3.el6.x86_64/kernel/drivers/scsi/
      echo "modprobe hpvsa" > etc/modprobe.d/hpvsa.conf


    To get more information on how to pass options to
    the module, start dependent modules or black-list modules please,
    consult see the *modprobe.d* man page.

    ::

        vi etc/modprobe.d/blacklist.conf

#. Pack the intiramfs back to **initfamfs.img.new** image:

   ::

      find /tmp/initrd-orig/initramfs | cpio --quiet -o -H newc | gzip -9 > /tmp/initramfs.img.new

#. Clean up. Remove */tmp/initrd-orig* temporary folder:

   ::

      rm -Rf /tmp/initrd-orig/


Creating a custom bootstrap node
--------------------------------

This option requires further investigation
and will be introduced in the near future.


Replacing default bootstrap node with the custom one
++++++++++++++++++++++++++++++++++++++++++++++++++++

Let's suppose that you have created or modified
the initramfs image. It is placed in the */tmp* folder under **initramfs.img.new** name.

To replace the default boostrap with the custom,
follow these steps:

#. Save the previous initramfs image:

   ::

       mv /var/www/nailgun/bootstrap/initramfs.img /var/www/nailgun/bootstrap/initramfs.img.old


#. Copy the new initramfs image into the bootstrap folder:

   ::

      cd /tmp
      cp initramfs.img.new /var/www/nailgun/bootstrap/initramfs.img
      dockerctl copy /var/www/nailgun/bootstrap/initramfs.img cobbler:/var/lib/tftpboot/images/bootstrap/initramfs.img

#. Make the Cobbler update the files:

   ::

      cobbler sync



