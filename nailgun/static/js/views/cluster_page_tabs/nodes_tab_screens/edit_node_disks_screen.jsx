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
define(
[
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'react',
    'utils',
    'models',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function($, _, i18n, Backbone, React, utils, models, ComponentMixins, controls) {
    'use strict';

    var EditNodeDisksScreen = React.createClass({
        mixins: [
            ComponentMixins.nodeConfigurationScreenMixin,
            ComponentMixins.backboneMixin('cluster', 'change:status change:nodes sync'),
            ComponentMixins.backboneMixin('nodes', 'change sync'),
            ComponentMixins.backboneMixin('disks', 'reset change:volumes')
        ],
        statics: {
            fetchData: function(options) {
                var cluster = options.cluster,
                    nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);}),
                    nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));
                if (nodes.length != nodeIds.length) {
                    utils.showErrorDialog({
                        title: i18n('cluster_page.nodes_tab.node_loading_error.title'),
                        message: i18n('cluster_page.nodes_tab.node_loading_error.load_error')
                    });
                    //FIXME: same issue as on edit_node_interfaces_screeen - impossible navigate to NodeList (in current master is the same issue)
                    ComponentMixins.nodeConfigurationScreenMixin.goToNodeList(cluster);
                    return;
                }

                var volumes = new models.Volumes();
                volumes.url = _.result(nodes.at(0), 'url') + '/volumes';
                return $.when.apply($, nodes.map(function(node) {
                        node.disks = new models.Disks();
                        return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
                    }, this).concat(volumes.fetch()))
                    .then(function() {
                        var disks = new models.Disks(_.cloneDeep(nodes.at(0).disks.toJSON()), {parse: true});
                        return {
                            disks: disks,
                            nodes: nodes,
                            volumes: volumes
                        };
                    });
            }
        },
        getInitialState: function() {
            return {actionInProgress: false};
        },
        hasChanges: function() {
            var volumes = _.pluck(this.props.disks.toJSON(), 'volumes');
            return this.props.nodes.any(function(node) {
                return !_.isEqual(volumes, _.pluck(node.disks.toJSON(), 'volumes'));
            });
        },
        hasValidationErrors: function() {
            return this.props.disks.any(function(disk) {
                return disk.validationError || disk.get('volumes').some('validationError');
            });
        },
        isLocked: function() {
            var hasLockedNodes = this.props.nodes.any(function(node) {
                return !node.get('pending_addition') || _.contains(['ready', 'error'], node.get('status'));
            });
            return hasLockedNodes || this.isLockedScreen();
        },
        loadDefaults: function() {
            this.setState({actionInProgress: true});
            this.props.disks.fetch({url: _.result(this.props.nodes.at(0), 'url') + '/disks/defaults/'})
                .fail(_.bind(function(response) {
                    var ns = 'cluster_page.nodes_tab.configure_disks.configuration_error.';
                    utils.showErrorDialog({
                        title: i18n(ns + 'title'),
                        message: utils.getResponseText(response) || i18n(ns + 'load_defaults_warning')
                    });
                }, this))
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        revertChanges: function() {
            this.props.disks.reset(_.cloneDeep(this.props.nodes.at(0).disks.toJSON()), {parse: true});
        },
        applyChanges: function() {
            this.setState({actionInProgress: true});
            return $.when.apply($, this.props.nodes.map(function(node) {
                    node.disks.each(function(disk, index) {
                        disk.set({volumes: new models.Volumes(this.props.disks.at(index).get('volumes').toJSON())});
                    }, this);
                    return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .fail(_.bind(function(response) {
                    var ns = 'cluster_page.nodes_tab.configure_disks.configuration_error.';
                    utils.showErrorDialog({
                        title: i18n(ns + 'title'),
                        message: utils.getResponseText(response) || i18n(ns + 'saving_warning')
                    });
                }, this))
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        getDiskMetaData: function(disk) {
            var result,
                disksMetaData = this.props.nodes.at(0).get('meta').disks;
            // try to find disk metadata by matching "extra" field
            // if at least one entry presents both in disk and metadata entry,
            // this metadata entry is for our disk
            var extra = disk.get('extra') || [];
            result = _.find(disksMetaData, function(diskMetaData) {
                return _.isArray(diskMetaData.extra) && _.intersection(diskMetaData.extra, extra).length;
            }, this);
            // if matching "extra" fields doesn't work, try to search by disk id
            if (!result) {
                result = _.find(disksMetaData, {disk: disk.id});
            }
            return result;
        },
        getVolumesInfo: function(disk) {
            var volumes = {},
                unallocatedWidth = 100;
            disk.get('volumes').each(function(volume) {
                var size = volume.get('size') || 0,
                    width = this.getVolumeWidth(disk, size),
                    name = volume.get('name');
                unallocatedWidth -= width;
                volumes[name] = {
                    size: size,
                    width: width
                };
            }, this);
            volumes.unallocated = {
                size: disk.getUnallocatedSpace(),
                width: unallocatedWidth
            };
            return volumes;
        },
        getVolumeWidth: function(disk, size) {
            return disk.get('size') ? utils.floor(size / disk.get('size') * 100, 2) : 0;
        },
        refresh: function() {
            this.forceUpdate();
        },
        render: function() {
            var locked = this.isLocked(),
                hasChanges = this.hasChanges(),
                hasErrors = this.hasValidationErrors(),
                loadDefaultsEnabled = !this.state.actionInProgress && !locked,
                revertChangesEnabled = !this.state.actionInProgress && hasChanges,
                applyEnabled = !hasErrors && !this.state.actionInProgress && hasChanges;
            return (
                <div className='edit-node-disks-screen'>
                    <div className='row'>
                        <div className='title'>
                            {i18n('cluster_page.nodes_tab.configure_disks.title', {count: this.props.nodes.length, name: this.props.nodes.length && this.props.nodes.at(0).get('name')})}
                        </div>
                        <div className='col-xs-12 node-disks'>
                            {this.state.actionInProgress && <controls.ProgressBar />}
                            {this.props.disks.map(function(disk, index) {
                                return (<NodeDisk
                                    disk={disk}
                                    key={index}
                                    refresh={this.refresh}
                                    disabled={this.state.actionInProgress}
                                    volumes={this.props.volumes}
                                    volumesInfo={this.getVolumesInfo(disk)}
                                    diskMetaData={this.getDiskMetaData(disk)}
                                />);
                            }, this)}
                        </div>
                        <div className='col-xs-12 page-buttons'>
                            <div className='well clearfix'>
                                <div className='btn-group'>
                                    <button onClick={this.returnToNodeList} className='btn btn-default btn-return'>{i18n('cluster_page.nodes_tab.back_to_nodes_button')}</button>
                                </div>
                                <div className='btn-group pull-right'>
                                    <button className='btn btn-default btn-defaults' onClick={this.loadDefaults} disabled={!loadDefaultsEnabled}>{i18n('common.load_defaults_button')}</button>
                                    <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={!revertChangesEnabled}>{i18n('common.cancel_changes_button')}</button>
                                    <button className='btn btn-success btn-apply' onClick={this.applyChanges} disabled={!applyEnabled}>{i18n('common.apply_button')}</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    var NodeDisk = React.createClass({
        mixins: [
            ComponentMixins.backboneMixin('disk', 'change invalid')
        ],
        getInitialState: function() {
            return {};
        },
        componentDidMount: function() {
            $('.disk-details', this.getDOMNode())
                .on('show.bs.collapse', this.setState.bind(this, {collapsed: true}, null))
                .on('hide.bs.collapse', this.setState.bind(this, {collapsed: false}, null));
        },
        updateDisk: function(name, value) {
            var disk = this.props.disk,
                size = parseInt(value),
                volume = disk.get('volumes').findWhere({name: name}),
                maxSize = volume.getMaxSize(),
                minSize = volume.getMinimalSize(this.props.volumes.findWhere({name: name}).get('min_size')),
                ns = 'cluster_page.nodes_tab.configure_disks.configuration_notice.',
                notice = {};
            if (size > maxSize) {
                size = maxSize;
                notice[name] = i18n(ns + 'maximum', {count: utils.formatNumber(maxSize)});
            } else if (size < minSize) {
                size = minSize;
                notice[name] = i18n(ns + 'minimum', {count: utils.formatNumber(minSize)});
            }
            volume.set({size: size}, {validate: true, minimum: minSize});
            this.setState({notice: notice});
            this.props.refresh();
        },
        render: function() {
            var disk = this.props.disk,
                volumesInfo = this.props.volumesInfo,
                diskMetaData = this.props.diskMetaData,
                sortOrder = ['name', 'model', 'size'];
            return (
                <div className='col-xs-12 disk-box' data-disk={disk.id} key={this.props.key}>
                    <div className='row'>
                        <h4 className='col-xs-6'>
                            {disk.get('name')} ({disk.id})
                        </h4>
                        <h4 className='col-xs-6 text-right'>
                            {i18n('cluster_page.nodes_tab.configure_disks.total_space')} : {utils.showDiskSize(disk.get('size'), 2)}
                        </h4>
                    </div>
                    <div className='row disk-visual clearfix'>
                        {this.props.volumes.map(function(volume, index) {
                            var volumeName = volume.get('name'),
                                showRemoveButton = disk.get('volumes').findWhere({name: volumeName}).getMinimalSize(volume.get('min_size')) <= 0,
                                closeButtonclasses = {
                                    'close-btn': true,
                                    hide: !showRemoveButton || !this.state.collapsed
                                };
                            return (
                                <div className={'volume-group pull-left volume_type_' + (index + 1)} data-volume={volumeName} key={'volume_' + volumeName} style={{width: volumesInfo[volumeName].width + '%'}}>
                                    <div className='text-center' data-toggle='collapse' data-target={'#' + disk.get('name')}>
                                        <div>{volume.get('label')}</div>
                                        <div className='volume-group-size'>{utils.showDiskSize(volumesInfo[volumeName].size, 2)}</div>
                                    </div>
                                    <div className={utils.classNames(closeButtonclasses)} onClick={_.partial(this.updateDisk, volumeName, 0)} name={volumeName}>&times;</div>
                                </div>
                            );
                        }, this)}
                        <div className={'volume-group pull-left'} data-volume='unallocated' style={{width: volumesInfo.unallocated.width + '%'}}>
                            <div className='text-center' data-toggle='collapse' data-target={'#' + disk.get('name')}>
                                <div className='volume-group-name'>{i18n('cluster_page.nodes_tab.configure_disks.unallocated')}</div>
                                <div className='volume-group-size'>{utils.showDiskSize(volumesInfo.unallocated.size, 2)}</div>
                            </div>
                        </div>
                    </div>
                    <div className='row collapse disk-details' id={disk.get('name')} key='diskDetails' ref={disk.get('name')}>
                        <div className='col-xs-5'>
                            {diskMetaData &&
                                <div>
                                    <h5>{i18n('cluster_page.nodes_tab.configure_disks.disk_information')}</h5>
                                    <div className='form-horizontal disk-info-box'>
                                        {_.map(utils.sortEntryProperties(diskMetaData, sortOrder), function(propertyName) {
                                            return (
                                                <div className='form-group' key={'property_' + propertyName}>
                                                    <label className='col-xs-2'>{propertyName.replace(/_/g, ' ')}</label>
                                                    <div className='col-xs-10'>
                                                        <p className='form-control-static'>
                                                            {propertyName == 'size' ? utils.showDiskSize(diskMetaData[propertyName]) : diskMetaData[propertyName]}
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
                            <h5>{i18n('cluster_page.nodes_tab.configure_disks.volume_groups')}</h5>
                            <div className='form-horizontal disk-utility-box'>
                                {this.props.volumes.map(function(volume, index) {
                                    var volumeName = volume.get('name'),
                                        value = volumesInfo[volumeName].size || 0,
                                        currentVolume = disk.get('volumes').findWhere({name: volumeName}),
                                        currentMaxSize = currentVolume.getMaxSize(),
                                        currentMinSize = _.max([currentVolume.getMinimalSize(volume.get('min_size')), 0]),
                                        inputClasses = {
                                            'has-error': !!currentVolume.validationError,
                                            'col-xs-3 volume-group-input': true
                                        };
                                    return (
                                        <div key={'edit_' + volumeName}>
                                            <div className='form-group volume-group row' data-volume={volumeName}>
                                                <label className='col-xs-4'>
                                                    <span ref={'volume-group-flag ' + volumeName} className={'volume_type_' + (index + 1)}> &nbsp; </span>
                                                    {volume.get('label')}
                                                </label>
                                                <div className='col-xs-4 volume-group-range'>
                                                    {/* key needs here for corrects rendering input in Chrome browser */}
                                                    <controls.Input
                                                        key={currentMaxSize + currentMinSize}
                                                        type='range'
                                                        wrapperClassName={currentMaxSize == currentMinSize && 'hide'}
                                                        onInput={this.updateDisk}
                                                        name={volumeName}
                                                        min='0'
                                                        max={currentMaxSize}
                                                        defaultValue={value}
                                                        disabled={this.props.disabled}
                                                    />
                                                </div>
                                                <controls.Input
                                                    type='number'
                                                    onChange={this.updateDisk}
                                                    wrapperClassName={utils.classNames(inputClasses)}
                                                    name={volumeName}
                                                    min='0'
                                                    max={disk.get('size')}
                                                    value={value}
                                                    disabled={this.props.disabled || currentMaxSize == currentMinSize}
                                                />
                                                <div className='col-xs-1 volume-group-size-label'>{i18n('common.size.mb')}</div>
                                            </div>
                                            {this.state.notice && this.state.notice[volumeName] &&
                                                <div className='volume-group-notice text-right'>{this.state.notice[volumeName]}</div>
                                            }
                                        </div>
                                    );
                                }, this)}
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return EditNodeDisksScreen;
});
