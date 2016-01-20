/*
 * Copyright 2015 Mirantis, Inc.
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
import $ from 'jquery';
import _ from 'underscore';
import Backbone from 'backbone';
import i18n from 'i18n';
import React from 'react';
import ReactDOM from 'react-dom';
import utils from 'utils';
import models from 'models';
import {backboneMixin, unsavedChangesMixin} from 'component_mixins';
import {Input} from 'views/controls';

var EditNodeDisksScreen = React.createClass({
  mixins: [
    backboneMixin('cluster', 'change:status change:nodes sync'),
    backboneMixin('nodes', 'change sync'),
    backboneMixin('disks', 'reset change'),
    unsavedChangesMixin
  ],
  statics: {
    fetchData(options) {
      var nodes = utils.getNodeListFromTabOptions(options);

      if (!nodes || !nodes.areDisksConfigurable()) {
        return $.Deferred().reject();
      }

      var volumes = new models.Volumes();
      volumes.url = _.result(nodes.at(0), 'url') + '/volumes';
      return $.when(...nodes.map((node) => {
        node.disks = new models.Disks();
        return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
      }, this).concat(volumes.fetch()))
        .then(() => {
          var disks = new models.Disks(_.cloneDeep(nodes.at(0).disks.toJSON()), {parse: true});
          return {
            disks: disks,
            nodes: nodes,
            volumes: volumes
          };
        });
    }
  },
  getInitialState() {
    return {actionInProgress: false};
  },
  componentWillMount() {
    this.updateInitialData();
  },
  isLocked() {
    return !!this.props.cluster.task({group: 'deployment', active: true}) ||
      !_.all(this.props.nodes.invoke('areDisksConfigurable'));
  },
  updateInitialData() {
    this.setState({initialDisks: _.cloneDeep(this.props.nodes.at(0).disks.toJSON())});
  },
  hasChanges() {
    return !this.isLocked() && !_.isEqual(_.pluck(this.props.disks.toJSON(), 'volumes'), _.pluck(this.state.initialDisks, 'volumes'));
  },
  loadDefaults() {
    this.setState({actionInProgress: true});
    this.props.disks.fetch({url: _.result(this.props.nodes.at(0), 'url') + '/disks/defaults/'})
      .fail((response) => {
        var ns = 'cluster_page.nodes_tab.configure_disks.configuration_error.';
        utils.showErrorDialog({
          title: i18n(ns + 'title'),
          message: utils.getResponseText(response) || i18n(ns + 'load_defaults_warning')
        });
      })
      .always(() => {
        this.setState({actionInProgress: false});
      });
  },
  revertChanges() {
    this.props.disks.reset(_.cloneDeep(this.state.initialDisks), {parse: true});
  },
  applyChanges() {
    if (!this.isSavingPossible()) return $.Deferred().reject();

    this.setState({actionInProgress: true});
    return $.when(...this.props.nodes.map((node) => {
      node.disks.each((disk, index) => {
        disk.set({volumes: new models.Volumes(this.props.disks.at(index).get('volumes').toJSON())});
      });
      return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
    }))
      .done(this.updateInitialData)
      .fail((response) => {
        var ns = 'cluster_page.nodes_tab.configure_disks.configuration_error.';
        utils.showErrorDialog({
          title: i18n(ns + 'title'),
          message: utils.getResponseText(response) || i18n(ns + 'saving_warning')
        });
      })
      .always(() => {
        this.setState({actionInProgress: false});
      });
  },
  getDiskMetaData(disk) {
    var result;
    var disksMetaData = this.props.nodes.at(0).get('meta').disks;
    // try to find disk metadata by matching "extra" field
    // if at least one entry presents both in disk and metadata entry,
    // this metadata entry is for our disk
    var extra = disk.get('extra') || [];
    result = _.find(disksMetaData, (diskMetaData) =>
      _.isArray(diskMetaData.extra) && _.intersection(diskMetaData.extra, extra).length
    );
    // if matching "extra" fields doesn't work, try to search by disk id
    if (!result) {
      result = _.find(disksMetaData, {disk: disk.id});
    }
    return result;
  },
  getVolumesInfo(disk) {
    var volumes = {};
    var unallocatedWidth = 100;
    disk.get('volumes').each((volume) => {
      var size = volume.get('size') || 0;
      var width = this.getVolumeWidth(disk, size);
      var name = volume.get('name');
      unallocatedWidth -= width;
      volumes[name] = {
        size: size,
        width: width,
        max: volume.getMaxSize(),
        min: volume.getMinimalSize(this.props.volumes.findWhere({name: name}).get('min_size')),
        error: volume.validationError
      };
    });
    volumes.unallocated = {
      size: disk.getUnallocatedSpace(),
      width: unallocatedWidth
    };
    return volumes;
  },
  getVolumeWidth(disk, size) {
    return disk.get('size') ? utils.floor(size / disk.get('size') * 100, 2) : 0;
  },
  hasErrors() {
    return this.props.disks.any((disk) =>
      disk.get('volumes').any('validationError')
    );
  },
  isSavingPossible() {
    return !this.state.actionInProgress && this.hasChanges() && !this.hasErrors();
  },
  render() {
    var hasChanges = this.hasChanges();
    var locked = this.isLocked();
    var loadDefaultsDisabled = !!this.state.actionInProgress;
    var revertChangesDisabled = !!this.state.actionInProgress || !hasChanges;
    return (
      <div className='edit-node-disks-screen'>
        <div className='row'>
          <div className='title'>
            {i18n('cluster_page.nodes_tab.configure_disks.' + (locked ? 'read_only_' : '') + 'title', {count: this.props.nodes.length, name: this.props.nodes.length && this.props.nodes.at(0).get('name')})}
          </div>
          <div className='col-xs-12 node-disks'>
            {this.props.disks.length ?
              this.props.disks.map((disk, index) => {
                return (<NodeDisk
                  disk={disk}
                  key={index}
                  disabled={locked || this.state.actionInProgress}
                  volumes={this.props.volumes}
                  volumesInfo={this.getVolumesInfo(disk)}
                  diskMetaData={this.getDiskMetaData(disk)}
                />);
              })
            :
              <div className='alert alert-warning'>
                {i18n('cluster_page.nodes_tab.configure_disks.no_disks', {count: this.props.nodes.length})}
              </div>
            }
          </div>
          <div className='col-xs-12 page-buttons content-elements'>
            <div className='well clearfix'>
              <div className='btn-group'>
                <a className='btn btn-default' href={'#cluster/' + this.props.cluster.id + '/nodes'} disabled={this.state.actionInProgress}>
                  {i18n('cluster_page.nodes_tab.back_to_nodes_button')}
                </a>
              </div>
              {!locked && !!this.props.disks.length &&
                <div className='btn-group pull-right'>
                  <button className='btn btn-default btn-defaults' onClick={this.loadDefaults} disabled={loadDefaultsDisabled}>{i18n('common.load_defaults_button')}</button>
                  <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={revertChangesDisabled}>{i18n('common.cancel_changes_button')}</button>
                  <button className='btn btn-success btn-apply' onClick={this.applyChanges} disabled={!this.isSavingPossible()}>{i18n('common.apply_button')}</button>
                </div>
              }
            </div>
          </div>
        </div>
      </div>
    );
  }
});

var NodeDisk = React.createClass({
  getInitialState() {
    return {collapsed: true};
  },
  componentDidMount() {
    $('.disk-details', ReactDOM.findDOMNode(this))
      .on('show.bs.collapse', this.setState.bind(this, {collapsed: true}, null))
      .on('hide.bs.collapse', this.setState.bind(this, {collapsed: false}, null));
  },
  updateDisk(name, value) {
    var size = parseInt(value, 10) || 0;
    var volumeInfo = this.props.volumesInfo[name];
    if (size > volumeInfo.max) {
      size = volumeInfo.max;
    }
    this.props.disk.get('volumes').findWhere({name: name}).set({size: size}).isValid({minimum: volumeInfo.min});
    this.props.disk.trigger('change', this.props.disk);
  },
  toggleDisk(name) {
    $(ReactDOM.findDOMNode(this.refs[name])).collapse('toggle');
  },
  render() {
    var disk = this.props.disk;
    var volumesInfo = this.props.volumesInfo;
    var diskMetaData = this.props.diskMetaData;
    var requiredDiskSize = _.sum(disk.get('volumes').map((volume) => {
      return volume.getMinimalSize(this.props.volumes.findWhere({name: volume.get('name')}).get('min_size'));
    }));
    var diskError = disk.get('size') < requiredDiskSize;
    var sortOrder = ['name', 'model', 'size'];
    var ns = 'cluster_page.nodes_tab.configure_disks.';

    return (
      <div className='col-xs-12 disk-box' data-disk={disk.id} key={this.props.key}>
        <div className='row'>
          <h4 className='col-xs-6'>
            {disk.get('name')} ({disk.id})
          </h4>
          <h4 className='col-xs-6 text-right'>
            {i18n(ns + 'total_space')} : {utils.showDiskSize(disk.get('size'), 2)}
          </h4>
        </div>
        <div className='row disk-visual clearfix'>
          {this.props.volumes.map((volume, index) => {
            var volumeName = volume.get('name');
            return (
              <div
                key={'volume_' + volumeName}
                ref={'volume_' + volumeName}
                className={'volume-group pull-left volume-type-' + (index + 1)}
                data-volume={volumeName}
                style={{width: volumesInfo[volumeName].width + '%'}}
              >
                <div className='text-center toggle' onClick={_.partial(this.toggleDisk, disk.get('name'))}>
                  <div>{volume.get('label')}</div>
                  <div className='volume-group-size'>
                    {utils.showDiskSize(volumesInfo[volumeName].size, 2)}
                  </div>
                </div>
                {!this.props.disabled && volumesInfo[volumeName].min <= 0 && this.state.collapsed &&
                  <div className='close-btn' onClick={_.partial(this.updateDisk, volumeName, 0)}>&times;</div>
                }
              </div>
            );
          })}
          <div className='volume-group pull-left' data-volume='unallocated' style={{width: volumesInfo.unallocated.width + '%'}}>
            <div className='text-center toggle' onClick={_.partial(this.toggleDisk, disk.get('name'))}>
              <div className='volume-group-name'>{i18n(ns + 'unallocated')}</div>
              <div className='volume-group-size'>{utils.showDiskSize(volumesInfo.unallocated.size, 2)}</div>
            </div>
          </div>
        </div>
        <div className='row collapse disk-details' id={disk.get('name')} key='diskDetails' ref={disk.get('name')}>
          <div className='col-xs-5'>
            {diskMetaData &&
              <div>
                <h5>{i18n(ns + 'disk_information')}</h5>
                <div className='form-horizontal disk-info-box'>
                  {_.map(utils.sortEntryProperties(diskMetaData, sortOrder), (propertyName) => {
                    return (
                      <div className='form-group' key={'property_' + propertyName}>
                        <label className='col-xs-2'>{propertyName.replace(/_/g, ' ')}</label>
                        <div className='col-xs-10'>
                          <p className='form-control-static'>
                            {propertyName === 'size' ? utils.showDiskSize(diskMetaData[propertyName]) : diskMetaData[propertyName]}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            }
          </div>
          <div className='col-xs-7'>
            <h5>{i18n(ns + 'volume_groups')}</h5>
            <div className='form-horizontal disk-utility-box'>
              {this.props.volumes.map((volume, index) => {
                var volumeName = volume.get('name');
                var value = volumesInfo[volumeName].size;
                var currentMaxSize = volumesInfo[volumeName].max;
                var currentMinSize = _.max([volumesInfo[volumeName].min, 0]);
                var validationError = volumesInfo[volumeName].error;

                var props = {
                  name: volumeName,
                  min: currentMinSize,
                  max: currentMaxSize,
                  disabled: this.props.disabled || currentMaxSize <= currentMinSize
                };

                return (
                  <div key={'edit_' + volumeName} data-volume={volumeName}>
                    <div className='form-group volume-group row'>
                      <label className='col-xs-4 volume-group-label'>
                        <span ref={'volume-group-flag ' + volumeName} className={'volume-type-' + (index + 1)}> &nbsp; </span>
                        {volume.get('label')}
                      </label>
                      <div className='col-xs-4 volume-group-range'>
                        <Input {...props}
                          type='range'
                          ref={'range-' + volumeName}
                          onChange={_.partialRight(this.updateDisk)}
                          value={value}
                        />
                      </div>
                      <Input {...props}
                        type='number'
                        wrapperClassName='col-xs-3 volume-group-input'
                        onChange={_.partialRight(this.updateDisk)}
                        error={validationError && ''}
                        value={value}
                      />
                      <div className='col-xs-1 volume-group-size-label'>{i18n('common.size.mb')}</div>
                    </div>
                    {!!value && value === currentMinSize &&
                      <div className='volume-group-notice text-info'>{i18n(ns + 'minimum_reached')}</div>
                    }
                    {validationError &&
                      <div className='volume-group-notice text-danger'>{validationError}</div>
                    }
                  </div>
                );
              })}
              {diskError &&
                <div className='volume-group-notice text-danger'>{i18n(ns + 'not_enough_space')}</div>
              }
            </div>
          </div>
        </div>
      </div>
    );
  }
});

export default EditNodeDisksScreen;
