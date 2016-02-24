/*
 * Copyright 2016 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/

define([
  'tests/functional/helpers'
], function() {
  'use strict';

  function SettingsLib(remote) {
    this.remote = remote;
  }

  SettingsLib.prototype = {
    constructor: SettingsLib,

    gotoOpenStackSettings: function(settingsSegmentName) {
      var segmentName = (settingsSegmentName.toLowerCase()).replace(' ', '_') + ' ';
      var listSelector = 'ul.nav-pills.nav-stacked ';
      var segmentSelector = 'a.subtab-link-' + segmentName;
      var pageSelector = 'div.' + segmentName;
      var activeSelector = 'li.active ';
      var segmentDescription = RegExp(settingsSegmentName, 'i');
      return this.remote
        .assertElementsExist(listSelector, 'Default settings segment list exists')
        .assertElementsExist(segmentSelector, settingsSegmentName +
          ' settings segment link exists')
        .clickByCssSelector(segmentSelector)
        .assertElementsAppear(pageSelector, 2000, settingsSegmentName +
          ' settings segment page is loaded')
        .assertElementsExist(activeSelector + segmentSelector, settingsSegmentName +
          ' settings segment link exists and active')
        .assertElementMatchesRegExp(activeSelector + segmentSelector, segmentDescription,
          settingsSegmentName + ' settings segment link name is correct');
    },
    checkGeneralSegment: function() {
      var accessSelector = 'div.setting-section-access';
      var repositoriesSelector = 'div.setting-section-repo_setup';
      var kernelSelector = 'div.setting-section-kernel_params';
      var provisionSelector = 'div.setting-section-provision';
      return this.remote
        // Check Access subgroup
        .assertElementsExist(accessSelector, 'Access subgroup exists')
        .findByCssSelector(accessSelector)
          .assertElementMatchesRegExp('h3', /Access/i, 'Default subgroup name is observed')
          .assertElementEnabled('input[name="user"]', '"Username" textfield enabled')
          .assertElementEnabled('input[name="password"]', '"Password" textfield enabled')
          .assertElementEnabled('input[name="tenant"]', '"Tenant" textfield enabled')
          .assertElementEnabled('input[name="email"]', '"Email" textfield enabled')
          .end()
        // Check Repositories subgroup
        .assertElementsExist(repositoriesSelector, 'Repositories subgroup exists')
        .findByCssSelector(repositoriesSelector)
          .assertElementMatchesRegExp('h3', /Repositories/i, 'Default subgroup name is observed')
          .assertElementContainsText('span.help-block',
            'Please note: the first repository will be considered the operating system mirror ' +
            'that will be used during node provisioning.\nTo create a local repository mirror on ' +
            'the Fuel master node, please follow the instructions provided by running ' +
            '"fuel-createmirror --help" on the Fuel master node.\nPlease make sure your Fuel ' +
            'master node has Internet access to the repository before attempting to create a ' +
            'mirror.\nFor more details, please refer to the documentation (https://docs.mirantis' +
            '.com/openstack/fuel/fuel-9.0/operations.html#external-ubuntu-ops).',
            'Default subgroup description is observed')
          .assertElementsExist('div.repo-name', 8,
            'Default quantity of Name textfields is observed')
          .assertElementsExist('div.repo-uri', 8,
            'Default quantity of URI textfields is observed')
          .assertElementsExist('div.repo-priority', 8,
            'Default quantity of Priority textfields is observed')
          .assertElementEnabled('button.btn-add-repo', '"Add Extra Repo" button enabled')
          .end()
        // Check Kernel parameters subgroup
        .assertElementsExist(kernelSelector, 'Kernel parameters subgroup exists')
        .findByCssSelector(kernelSelector)
          .assertElementMatchesRegExp('h3', /Kernel parameters/i,
            'Default subgroup name is observed')
          .assertElementEnabled('input[name="kernel"]', '"Initial parameters" textfield enabled')
          .end()
        // Check Provision subgroup
        .assertElementsExist(provisionSelector, 'Provision subgroup exists')
        .findByCssSelector(provisionSelector)
          .assertElementMatchesRegExp('h3', /Provision/i, 'Default subgroup name is observed')
          .assertElementEnabled('textarea[name="packages"]', '"Initial packages" textarea enabled')
          .end();
    },
    checkSecuritySegment: function() {
      var commonSelector = 'div.setting-section-common';
      var publicTlsSelector = 'div.setting-section-public_ssl';
      var servicesName = 'TLS for OpenStack public endpoints';
      var horizonName = 'HTTPS for Horizon';
      return this.remote
        // Check Common subgroup
        .assertElementsExist(commonSelector, 'Common subgroup exists')
        .findByCssSelector(commonSelector)
          .assertElementMatchesRegExp('h3', /Common/i, 'Default subgroup name is observed')
          .assertElementEnabled('textarea[name="auth_key"]', '"Public Key" textarea enabled')
          .end()
        // Check Public TLS subgroup
        .assertElementsExist(publicTlsSelector, 'Public TLS subgroup exists')
        .findByCssSelector(publicTlsSelector)
          .assertElementMatchesRegExp('h3', /Public TLS/i, 'Default subgroup name is observed')
          .findByCssSelector('div.checkbox-group')
            .assertElementEnabled('input[label="' + servicesName + '"]', '"' + servicesName +
              '" checkbox is enabled')
            .assertElementNotSelected('input[label="' + servicesName + '"]', '"' + servicesName +
              '" checkbox is not selected')
            .assertElementContainsText('label', servicesName, '"' + servicesName +
              '" label has default description')
            .assertElementContainsText('span.help-block',
              'Enable TLS termination on HAProxy for OpenStack services', '"' + servicesName +
              '" description has default value')
            .end()
          .findByCssSelector('div.checkbox-group.disabled')
            .assertElementDisabled('input[label="' + horizonName + '"]', '"' + horizonName +
              '" checkbox is disabled')
            .assertElementNotSelected('input[label="' + horizonName + '"]', '"' + horizonName +
              '" checkbox is not selected')
            .assertElementContainsText('label', horizonName, '"' + horizonName +
              '" label has default description')
            .assertElementContainsText('span.help-block',
              'Secure access to Horizon enabling HTTPS instead of HTTP', '"' + horizonName +
              '" description has default value')
            .end()
          .end();
    },
    checkComputeSegment: function() {
      var commonSelector = 'div.setting-section-common';
      var kvmSelector = 'input[value="kvm"]';
      var qemuSelector = 'input[value="qemu"]';
      var novaSelector = 'input[name="nova_quota"]';
      var stateSelector = 'input[name="resume_guests_state_on_host_boot"]';
      return this.remote
        // Check Common subgroup
        .assertElementsExist(commonSelector, 'Common subgroup exists')
        .findByCssSelector(commonSelector)
          .assertElementMatchesRegExp('h3', /Common/i, 'Default subgroup name is observed')
          .assertElementMatchesRegExp('h4', /Hypervisor type/i, 'Default name is observed')
          .assertElementEnabled(kvmSelector, '"KVM" radiobutton is enabled')
          .assertElementNotSelected(kvmSelector, '"KVM" radiobutton is not selected')
          .assertElementEnabled(qemuSelector, '"QEMU" radiobutton is enabled')
          .assertElementSelected(qemuSelector, '"QEMU" radiobutton is selected')
          .assertElementEnabled(novaSelector, '"Nova quotas" checkbox is enabled')
          .assertElementNotSelected(novaSelector, '"Nova quotas" checkbox is not selected')
          .assertElementEnabled(stateSelector,
            '"Resume guests state on host boot" checkbox is enabled')
          .assertElementSelected(stateSelector,
            '"Resume guests state on host boot" checkbox is selected')
          .end();
    },
    checkStorageSegment: function() {
      var commonSelector = 'div.setting-section-common';
      var storageSelector = 'div.setting-section-storage';
      var lvmSelector = 'input[name="volumes_lvm"]';
      var blockSelector = 'input[name="volumes_block_device"]';
      var cephSelector = 'input[name="volumes_ceph"]';
      var imagesSelector = 'input[name="images_ceph"]';
      var ephemeralSelector = 'input[name="ephemeral_ceph"]';
      var objectsSelector = 'input[name="objects_ceph"]';
      return this.remote
        // Check Common subgroup
        .assertElementsExist(commonSelector, 'Common subgroup exists')
        .findByCssSelector(commonSelector)
          .assertElementMatchesRegExp('h3', /Common/i, 'Default subgroup name is observed')
          .assertElementEnabled('input[name="use_cow_images"]',
            '"Use qcow format for images" checkbox is enabled')
          .assertElementSelected('input[name="use_cow_images"]',
            '"Use qcow format for images" checkbox is selected')
          .end()
        // Check Storage Backends subgroup
        .assertElementsExist(storageSelector, 'Storage Backends subgroup exists')
        .findByCssSelector(storageSelector)
          .assertElementMatchesRegExp('h3', /Storage Backends/i,
            'Default subgroup name is observed')
          .assertElementEnabled(lvmSelector,
            '"Cinder LVM over iSCSI for volumes" checkbox is enabled')
          .assertElementSelected(lvmSelector,
            '"Cinder LVM over iSCSI for volumes" checkbox is selected')
          .assertElementEnabled(blockSelector, '"Cinder Block device driver" checkbox is enabled')
          .assertElementNotSelected(blockSelector,
            '"Cinder Block device driver" checkbox is not selected')
          .assertElementDisabled(cephSelector,
            '"Ceph RBD for volumes (Cinder)" checkbox is disabled')
          .assertElementNotSelected(cephSelector,
            '"Ceph RBD for volumes (Cinder)" checkbox is not selected')
          .assertElementEnabled(imagesSelector,
            '"Ceph RBD for images (Glance)" checkbox is enabled')
          .assertElementNotSelected(imagesSelector,
            '"Ceph RBD for images (Glance)" checkbox is not selected')
          .assertElementEnabled(ephemeralSelector,
            '"Ceph RBD for ephemeral volumes (Nova)" checkbox is enabled')
          .assertElementNotSelected(ephemeralSelector,
            '"Ceph RBD for ephemeral volumes (Nova)" checkbox is not selected')
          .assertElementEnabled(objectsSelector,
            '"Ceph RadosGW for objects (Swift API)" checkbox is enabled')
          .assertElementNotSelected(objectsSelector,
            '"Ceph RadosGW for objects (Swift API)" checkbox is not selected')
          .assertElementEnabled('input[name="osd_pool_size"]',
            '"Ceph object replication factor" textfield is enabled')
          .end();
    },
    checkLoggingSegment: function() {
      var commonSelector = 'div.setting-section-common';
      var syslogSelector = 'div.setting-section-syslog';
      var puppetSelector = 'input[name="puppet_debug"]';
      var debugSelector = 'input[name="debug"]';
      var metadataSelector = 'input[name="metadata"]';
      var udpSelector = 'input[value="udp"]';
      var tcpSelector = 'input[value="tcp"]';
      return this.remote
        // Check Common subgroup
        .assertElementsExist(commonSelector, 'Common subgroup exists')
        .findByCssSelector(commonSelector)
          .assertElementMatchesRegExp('h3', /Common/i, 'Default subgroup name is observed')
          .assertElementEnabled(puppetSelector, '"Puppet debug logging" checkbox is enabled')
          .assertElementSelected(puppetSelector, '"Puppet debug logging" checkbox is selected')
          .assertElementEnabled(debugSelector, '"OpenStack debug logging" checkbox is enabled')
          .assertElementNotSelected(debugSelector,
            '"OpenStack debug logging" checkbox is not selected')
          .end()
        // Check Syslog subgroup
        .assertElementsExist(syslogSelector, 'Syslog subgroup exists')
        .findByCssSelector(syslogSelector)
          .assertElementMatchesRegExp('h3', /Syslog/i, 'Default subgroup name is observed')
          .assertElementEnabled(metadataSelector, '"Syslog" checkbox is enabled')
          .assertElementNotSelected(metadataSelector, '"Syslog" checkbox is not selected')
          .assertElementDisabled('input[name="syslog_server"]', '"Hostname" textfield is disabled')
          .assertElementDisabled('input[name="syslog_port"]', '"Port" textfield is disabled')
          .assertElementDisabled(udpSelector, '"UDP" radiobutton is disabled')
          .assertElementNotSelected(udpSelector, '"UDP" radiobutton is not selected')
          .assertElementDisabled(tcpSelector, '"TCP" radiobutton is disabled')
          .assertElementSelected(tcpSelector, '"TCP" radiobutton is selected')
          .end();
    },
    checkOpenStackServicesSegment: function() {
      var componentsSelector = 'div.setting-section-additional_components';
      var saharaSelector = 'input[name="sahara"]';
      var ceilometerSelector = 'input[name="ceilometer"]';
      var mongoSelector = 'input[name="mongo"]';
      var ironicSelector = 'input[name="ironic"]';
      return this.remote
        // Check Additional Components subgroup
        .assertElementsExist(componentsSelector, 'Additional Components subgroup exists')
        .findByCssSelector(componentsSelector)
          .assertElementMatchesRegExp('h3', /Additional Components/i,
            'Default subgroup name is observed')
          .assertElementEnabled(saharaSelector, '"Install Sahara" checkbox is enabled')
          .assertElementNotSelected(saharaSelector, '"Install Sahara" checkbox is not selected')
          .assertElementEnabled(ceilometerSelector, '"Install Ceilometer" checkbox is enabled')
          .assertElementNotSelected(ceilometerSelector,
            '"Install Ceilometer" checkbox is not selected')
          .assertElementDisabled(mongoSelector, '"Use external Mongo DB" checkbox is disabled')
          .assertElementNotSelected(mongoSelector,
            '"Use external Mongo DB" checkbox is not selected')
          .assertElementEnabled(ironicSelector, '"Install Ironic" checkbox is enabled')
          .assertElementNotSelected(ironicSelector, '"Install Ironic" checkbox is not selected')
          .end();
    },
    checkOtherSegment: function() {
      var vpnSelector = 'div.setting-section-VPNaaS';
      var zabbixSelector = 'div.setting-section-zabbix_monitoring';
      var loggingSelector = 'div.setting-section-logging';
      return this.remote
        // Check VPNaaS plugin for Neutron subgroup
        .assertElementsExist(vpnSelector, '"VPNaaS plugin" for Neutron subgroup exists')
        .findByCssSelector(vpnSelector)
          .assertElementMatchesRegExp('label', /VPNaaS plugin for Neutron/i,
            'Default subgroup name is observed')
          .assertElementDisabled('input[name="VPNaaS"]', '"Versions 1.1.0" radiobutton is disabled')
          .assertElementSelected('input[name="VPNaaS"]', '"Versions 1.1.0" radiobutton is selected')
          .end()
        // Check Zabbix for Fuel subgroup
        .assertElementsExist(zabbixSelector, 'Zabbix for Fuel subgroup exists')
        .findByCssSelector(zabbixSelector)
          .assertElementMatchesRegExp('label', /Zabbix for Fuel/i,
            'Default subgroup name is observed')
          .assertElementDisabled('input[label="1.0.0"]', '"Versions 1.0.0" radiobutton is disabled')
          .assertElementSelected('input[label="1.0.0"]', '"Versions 1.0.0" radiobutton is selected')
          .assertElementDisabled('input[label="2.0.0"]', '"Versions 2.0.0" radiobutton is disabled')
          .assertElementNotSelected('input[label="2.0.0"]',
            '"Versions 2.0.0" radiobutton is not selected')
          .assertElementDisabled('input[name="zabbix_text_1"]', '"label 1.1" textfield is disabled')
          .end()
        // Check The Logging, Monitoring and Alerting (LMA) Collector Plugin subgroup
        .assertElementsExist(loggingSelector,
          '"The Logging, Monitoring and Alerting (LMA) Collector Plugin" subgroup exists')
        .findByCssSelector(loggingSelector)
          .assertElementMatchesRegExp('label',
            /.*The Logging, Monitoring and Alerting.*LMA.*Collector Plugin.*/i,
            'Default subgroup name is observed')
          .assertElementDisabled('input[name="logging"]',
            '"Versions 0.7.0" radiobutton is disabled')
          .assertElementSelected('input[name="logging"]',
            '"Versions 0.7.0" radiobutton is selected')
          .assertElementDisabled('input[name="logging_text"]', '"label" textfield is disabled')
          .end();
    }
  };
  return SettingsLib;
});
