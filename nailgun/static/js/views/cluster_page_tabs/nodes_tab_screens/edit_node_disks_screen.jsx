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
    'jsx!views/dialogs',
    'jsx!views/controls'
],
function($, _, i18n, Backbone, React, utils, models, ComponentMixins, dialogs, controls) {
    'use strict';

    var EditNodeDisksScreen = React.createClass({
        mixins: [
            ComponentMixins.editNodesMixin,
            ComponentMixins.backboneMixin('cluster', 'change:status change:networkConfiguration change:nodes sync'),
            ComponentMixins.backboneMixin('nodes', 'change sync')
        ],
        statics: {
            fetchData: function(options) {
                var cluster = options.cluster,
                    nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);}),
                    nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds)),
                    nodeLoadingErrorNS = 'cluster_page.nodes_tab.node_loading_error.';
                if (nodes.length != nodeIds.length) {
                    utils.showErrorDialog({
                        title: i18n(nodeLoadingErrorNS + 'title'),
                        message: i18n(nodeLoadingErrorNS + 'load_error')
                    });
                    //FIXME: same issue as on edit_node_interfaces_screeen - impossible navigate to NodeList (in current master is the same issue)
                    ComponentMixins.editNodesMixin.goToNodeList(cluster);
                    return;
                }

                var volumes = new models.Volumes();
                volumes.url = _.result(nodes.at(0), 'url') + '/volumes';
                return $.when.apply($, nodes.map(function(node) {
                        node.disks = new models.Disks();
                        return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
                    }, this).concat(volumes.fetch()))
                    .then(function() {
                        return {
                            nodes: nodes,
                            volumes: volumes
                        };
                    });
            }
        },
        getInitialState: function() {
            return {
                disks: new models.Disks(_.cloneDeep(this.props.nodes.at(0).disks.toJSON()), {parse: true}),
                actionInProgress: false,
                resetData: false
            };
        },
        showDiscardChangesDialog: function() {
            dialogs.DiscardSettingsChangesDialog.show({cb: this.goToNodeList});
        },
        hasChanges: function() {
            var volumes = _.pluck(this.state.disks.toJSON(), 'volumes');
            return this.props.nodes.any(function(node) {
                return !_.isEqual(volumes, _.pluck(node.disks.toJSON(), 'volumes'));
            });
        },
        hasValidationErrors: function() {
            return this.state.disks.any(function(disk) {
                return disk.validationError || _.some(disk.get('volumes').models, 'validationError');
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
            this.state.disks.fetch({url: _.result(this.props.nodes.at(0), 'url') + '/disks/defaults/'})
                .fail(_.bind(function(response) {
                    var ns = 'cluster_page.nodes_tab.configure_disks.configuration_error.';
                    utils.showErrorDialog({
                        title: i18n(ns + 'title'),
                        message: utils.getResponseText(response) || i18n(ns + 'load_defaults_warning')
                    });
                }, this))
                .always(_.bind(function() {
                    this.setState({
                        actionInProgress: false,
                        resetData: true
                    });
                }, this));
        },
        revertChanges: function() {
            this.state.disks.reset(_.cloneDeep(this.props.nodes.at(0).disks.toJSON()), {parse: true});
            this.setState({resetData: true});
        },
        applyChanges: function() {
            return $.when.apply($, this.props.nodes.map(function(node) {
                    node.disks.each(function(disk, index) {
                        disk.set({volumes: new models.Volumes(this.state.disks.at(index).get('volumes').toJSON())});
                    }, this);
                    return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .done(_.bind(function() {
                    this.setState({resetData: true});
                }, this))
                .fail(_.bind(function(response) {
                    var ns = 'cluster_page.nodes_tab.configure_disks.configuration_error.';
                    utils.showErrorDialog({
                        title: i18n(ns + 'title'),
                        message: utils.getResponseText(response) || i18n(ns + 'saving_warning')
                    });
                }, this));
        },
        mapVolumesColors: function() {
            var volumesColors = {},
                alphabet = 'abcdefghi'.split('');
            this.props.volumes.each(function(volume, index) {
                volumesColors[volume.get('name')] = alphabet[index];
            }, this);
            volumesColors.unallocated = 'unallocated';
            return volumesColors;
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
        refreshDisks: function(disk) {
            this.state.disks.findWhere({id: disk.id}).set({volumes: disk.get('volumes')});
            this.setState({resetData: false});
        },
        render: function() {
            var locked = this.isLocked(),
                hasChanges = this.hasChanges(),
                hasErrors = this.hasValidationErrors(),
                volumesColors = this.mapVolumesColors(),
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
                            {this.state.disks.map(function(disk, index) {
                                return (<NodeDisk
                                    disk={disk}
                                    key={index}
                                    refreshDisks={this.refreshDisks}
                                    resetData={this.state.resetData}
                                    disabled={this.state.actionInProgress}
                                    volumes={this.props.volumes}
                                    diskMetaData={this.getDiskMetaData(disk)}
                                    volumesColors={volumesColors}
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
        getInitialState: function() {
            return {volumesInfo: this.getVolumesInfo()};
        },
        componentWillReceiveProps: function(nextProps) {
            if (nextProps.resetData) {
                this.setState({
                    volumesInfo: this.getVolumesInfo(nextProps.disk),
                    notice: {}
                });
            }
        },
        componentDidMount: function() {
            $('.disk-details', this.getDOMNode())
                .on('show.bs.collapse', this.setState.bind(this, {collapsed: true}, null))
                .on('hide.bs.collapse', this.setState.bind(this, {collapsed: false}, null));
        },
        getVolumesInfo: function(disk) {
            if (!disk) disk = this.props.disk;
            var volumes = {},
                unallocatedWidth = 100;
            disk.get('volumes').each(function(volume) {
                var size = volume.get('size') || 0,
                    width = this.getVolumeWidth(size),
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
        getVolumeWidth: function(size) {
            return this.props.disk.get('size') ? utils.floor(size / this.props.disk.get('size') * 100, 2) : 0;
        },
        updateDisk: function(name, value) {
            var disk = this.props.disk,
                size = parseInt(value),
                volume = disk.get('volumes').findWhere({name: name}),
                maxSize = volume.getMaxSize(),
                minSize = volume.getMinimalSize(this.props.volumes.findWhere({name: name}).get('min_size')),
                notice = {};
            if (size > maxSize) {
                size = maxSize;
                notice[name] = 'You have reached maximum allowed place: ' + utils.formatNumber(maxSize) + ' MB';
            } else if (size < minSize) {
                size = minSize;
                notice[name] = 'Minimal size for this volume is ' + utils.formatNumber(minSize) + ' MB';
            }
            volume.set({size: size}, {validate: true, minimum: minSize, maximum: true});
            disk.set({volumes: disk.get('volumes')}, {validate: true}); // disk validation (maximum)
            this.setState({
                volumesInfo: this.getVolumesInfo(),
                notice: notice
            });
            this.props.refreshDisks(disk);
        },
        render: function() {
            var disk = this.props.disk,
                volumesInfo = this.state.volumesInfo,
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
                        {this.props.volumes.map(function(volume) {
                            var volumeName = volume.get('name'),
                                showRemoveButton = disk.get('volumes').findWhere({name: volumeName}).getMinimalSize(volume.get('min_size')) <= 0,
                                closeButtonclasses = {
                                    'close-btn': true,
                                    hide: !showRemoveButton || !this.state.collapsed
                                };
                            return (
                                <div className={'volume-group pull-left volumes-color ' + this.props.volumesColors[volumeName]} data-volume={volumeName} key={'volume_' + volumeName} style={{width: volumesInfo[volumeName].width + '%'}}>
                                    <div className='text-center' data-toggle='collapse' data-target={'#' + disk.get('name')}>
                                        <div>{volume.get('label')}</div>
                                        <div className='volume-group-size'>{utils.showDiskSize(volumesInfo[volumeName].size, 2)}</div>
                                    </div>
                                    <div className={utils.classNames(closeButtonclasses)} onClick={_.partial(this.updateDisk, volumeName, 0)} name={volumeName}>&times;</div>
                                </div>
                            );
                        }, this)}
                        <div className={'volume-group pull-left volumes-color ' + this.props.volumesColors.unallocated} data-volume='unallocated' style={{width: volumesInfo.unallocated.width + '%'}}>
                            <div className='text-center' data-toggle='collapse' data-target={'#' + disk.get('name')}>
                                <div className='volume-group-name'>{i18n('cluster_page.nodes_tab.configure_disks.unallocated')}</div>
                                <div className='volume-group-size'>{utils.showDiskSize(volumesInfo.unallocated.size, 2)}</div>
                            </div>
                        </div>
                    </div>
                    <div className='row collapse disk-details' id={disk.get('name')} key='diskDetails' ref={disk.get('name')}>
                        <div className='col-xs-6'>
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
                        <div className='col-xs-6'>
                            <h5>{i18n('cluster_page.nodes_tab.configure_disks.volume_groups')}</h5>
                            <div className='form-horizontal disk-utility-box'>
                                {this.props.volumes.map(function(volume) {
                                    var volumeName = volume.get('name'),
                                        value = volumesInfo[volumeName].size || 0,
                                        diskInfo = disk.get('volumes').findWhere({name: volumeName}),
                                        inputClasses = {
                                            'has-error': !!diskInfo.validationError,
                                            'col-xs-4 volume-group-input': true
                                        };
                                    return (
                                        <div key={'edit_' + volumeName}>
                                            <div className='form-group volume-group row' data-volume={volumeName}>
                                                <label className='col-xs-4'>
                                                    <span ref={'volume-group-flag ' + volumeName} className={'volumes-color ' + this.props.volumesColors[volumeName]}> &nbsp; </span>
                                                    {volume.get('label')}
                                                </label>
                                                <div className='col-xs-3 volume-group-range'>
                                                    <controls.Input
                                                        type='range'
                                                        onChange={this.updateDisk}
                                                        name={volumeName}
                                                        min='0'
                                                        max={disk.get('size')}
                                                        value={value}
                                                        disabled={this.props.disabled}
                                                    />
                                                </div>
                                                <div className={utils.classNames(inputClasses)}>
                                                    <controls.Input
                                                        type='number'
                                                        onChange={this.updateDisk}
                                                        name={volumeName}
                                                        min='0'
                                                        max={disk.get('size')}
                                                        value={value}
                                                        disabled={this.props.disabled}
                                                    />
                                                </div>
                                                <div className='col-xs-1 volume-group-size-label'>{i18n('common.size.mb')}</div>
                                            </div>
                                            {diskInfo.validationError &&
                                                <div className='col-xs-12 volume-group-error text-right'>{diskInfo.validationError}</div>
                                            }
                                            {this.state.notice && this.state.notice[volumeName] &&
                                                <div className='col-xs-12 volume-group-notice text-right'>{this.state.notice[volumeName]}</div>
                                            }
                                        </div>
                                    );
                                }, this)}
                                <div className='volume-group-error common text-red text-right'></div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return EditNodeDisksScreen;
});
