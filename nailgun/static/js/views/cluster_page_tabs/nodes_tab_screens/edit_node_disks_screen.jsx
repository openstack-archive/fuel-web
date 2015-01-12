/*
 * Copyright 2013 Mirantis, Inc.
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
    'jquery-autoNumeric'
],
function($, _, i18n, Backbone, React, utils, models) {
    'use strict';

    var cx = React.addons.classSet;

    var ScreenMixin = {
        goToNodeList: function() {
            console.log('ScreenMixin goToNodeList');
            app.navigate('#cluster/' + this.props.cluster.get('id') + '/nodes', {trigger: true});
        },
        isLockedScreen: function() {
            return this.model && !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        },
        returnToNodeList: function() {
            if (this.hasChanges()) {
                app.page.discardSettingsChanges({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        }
    };

    var EditNodeDisksScreen = React.createClass({
        mixins: [
            ScreenMixin
        ],
        statics: {
            fetchData: function(options) {
                console.log(options);
                var cluster = options.cluster,
                    nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);}),
                    nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));
                console.log('this.nodes ', nodes );
                if (nodes.length) {
                    var volumes = new models.Volumes();
                    volumes.url = _.result(nodes.at(0), 'url') + '/volumes';
                    return $.when.apply($, nodes.map(function(node) {
                            node.disks = new models.Disks();
                            return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
                        }, this).concat(volumes.fetch()))
                        .then(_.bind(function() {
                            var disks = new models.Disks(_.cloneDeep(nodes.at(0).disks.toJSON()), {parse: true});
                            return {
                                nodes: nodes,
                                disks: disks,
                                volumes: volumes
                            };
                        }, this));
                } else ScreenMixin.goToNodeList();
            }
        },
        getInitialState: function() {
            return {
                disks: []
            };
        },
        componentWillMount: function() {
            
        },
        hasChanges: function() {
            // TODO understand what I need here this.state.disks or this.props.disks
            var volumes = _.pluck(this.props.disks.toJSON(), 'volumes');
            return !this.props.nodes.reduce(function(result, node) {
                return result && _.isEqual(volumes, _.pluck(node.disks.toJSON(), 'volumes'));
            }, true);
        },
        hasValidationErrors: function() {
            var result = false;
            this.props.disks.each(function(disk) {result = result || disk.validationError || _.some(disk.get('volumes').models, 'validationError');}, this);
            return result;
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.props.nodes.filter(function(node) {
                return node.get('pending_addition') || (node.get('status') == 'error' && node.get('error_type') == 'provision');
            });
            return !nodesAvailableForChanges.length || this.constructor.__super__.isLocked.apply(this);
        },
        loadDefaults: function() {
            this.setState({
                disks: this.props.disks
            });
        },
        revertChanges: function() {
            this.props.disks.reset(_.cloneDeep(this.props.nodes.at(0).disks.toJSON()), {parse: true});
        },
        applyChanges: function() {
            var cluster = this.props.cluster;
            if (this.hasValidationErrors()) {
                return (new $.Deferred()).reject();
            }
            return $.when.apply($, this.props.nodes.map(function(node) {
                    node.disks.each(function(disk, index) {
                        disk.set({volumes: new models.Volumes(this.state.disks.at(index).get('volumes').toJSON())});
                    }, this);
                    return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .done(_.bind(function() {
                    cluster.fetch();
                }, this))
                .fail(_.bind(function(response) {
                    this.checkForChanges();
                    utils.showErrorDialog({
                        title: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: utils.getResponseText(response) || i18n('cluster_page.nodes_tab.configure_disks.configuration_error.saving_warning')
                    });
                }, this));
        },
        mapVolumesColors: function() {
            var volumesColors = {},
                colors = [
                ['#23a85e', '#1d8a4d'],
                ['#3582ce', '#2b6ba9'],
                ['#eea616', '#c38812'],
                ['#1cbbb4', '#189f99'],
                ['#9e0b0f', '#870a0d'],
                ['#8f50ca', '#7a44ac'],
                ['#1fa0e3', '#1b88c1'],
                ['#85c329', '#71a623'],
                ['#7d4900', '#6b3e00']
            ];
            this.props.volumes.each(function(volume, index) {
                volumesColors[volume.get('name')] = colors[index];
            }, this);
            return volumesColors
        },
        getDiskMetaData: function(disk) {
            var result;
            var disksMetaData = this.props.nodes.at(0).get('meta').disks;
            // try to find disk metadata by matching "extra" field
            // if at least one entry presents both in disk and metadata entry,
            // this metadata entry is for our disk
            var extra = disk.get('extra') || [];
            result = _.find(disksMetaData, function(diskMetaData) {
                if (_.isArray(diskMetaData.extra)) {
                    return _.intersection(diskMetaData.extra, extra).length;
                }
                return false;
            }, this);

            // if matching "extra" fields doesn't work, try to search by disk id
            if (!result) {
                result = _.find(disksMetaData, {disk: disk.id});
            }

            return result;
        },
        render: function() {
            console.log('this.props', this.props);
            var nodes = this.props.nodes,
                disks = this.props.disks,
                volumesColors = this.mapVolumesColors();
            return (
                <div className='edit-node-disks'>
                    <h3>
                        {i18n('cluster_page.nodes_tab.configure_disks.title', {count: nodes.length, name: nodes.length && nodes.at(0).get('name')})}
                    </h3>
                    <div className="node-disks">
                    </div>
                    {disks && _.map(disks.models, function(disk, index) {
                        return (<NodeDisk
                            disk={disk}
                            index={'togglable_' + index}
                            volumes={this.props.volumes}
                            diskMetaData={this.getDiskMetaData(disk)}
                            disabled={this.props.disabled}
                            volumesColors={volumesColors}
                        />);
                    }, this)}
                    <div className="row">
                        <div className="page-control-box">
                            <div className="back-button pull-left">
                                <button onClick={this.returnToNodeList} className="btn btn-return">{i18n('cluster_page.nodes_tab.back_to_nodes_button')}</button>
                            </div>
                            <div className="page-control-button-placeholder">
                                <button onClick={this.loadDefaults} className="btn btn-defaults">{i18n('common.load_defaults_button')}</button>
                                <button onClick={this.revertChanges} className="btn btn-revert-changes">{i18n('common.cancel_changes_button')}</button>
                                <button onClick={this.applyChanges} className="btn btn-success btn-apply">{i18n('common.apply_button')}</button>
                            </div>
                        </div>
                    </div>
                </div>
                );
        }
    });

    var NodeDisk = React.createClass({
        volumeStylesTemplate: function(startColor, endColor) {
            return "background: " + startColor + "; " +
                "background: -moz-linear-gradient(top, " + startColor + " 0%, " + endColor + " 100%); " +
                "background: -webkit-gradient(linear, left top, left bottom, color-stop(0%," + startColor + "), color-stop(100%," + endColor + " )); " +
                "background: -webkit-linear-gradient(top, " + startColor + " 0%, " + endColor + " 100%); " +
                "background: -o-linear-gradient(top, " + startColor + " 0%, " + endColor + " 100%); " +
                "background: -ms-linear-gradient(top, " + startColor + " 0%, " + endColor + " 100%); " +
                "background: linear-gradient(to bottom, " + startColor + " 0%, " + endColor + " 100%); " +
                "bfilter: progid:DXImageTransform.Microsoft.gradient(startColorstr=" + startColor + ", endColorstr=" + endColor + ", GradientType=0);";
        },
        toggle: function(diskIndex) {
            $(this.refs[diskIndex].getDOMNode()).collapse('toggle');
        },
        tralala: function() {
            console.log('tralala');
        },
        renderVolume: function(name, width, size) {
            $(this.refs['volume_' + name].getDOMNode())
                .css('width', width + '%')
                .find('.volume-group-size').text(utils.showDiskSize(size, 2));
        },
        renderVisualGraph: function() {
            var disk = this.props.disk;
            if (!disk.get('volumes').some('validationError') && disk.isValid()) {
                var unallocatedWidth = 100;
                disk.get('volumes').each(function(volume) {
                    var width = disk.get('size') ? utils.floor(volume.get('size') / disk.get('size') * 100, 2) : 0;
                    unallocatedWidth -= width;
                    this.renderVolume(volume.get('name'), width, volume.get('size'));
                }, this);
                this.renderVolume('unallocated', unallocatedWidth, disk.getUnallocatedSpace());
            }
        },
        applyColors: function() {
            this.props.disk.get('volumes').each(function(volume) {
                var name = volume.get('name'),
                    colors = this.props.volumesColors[name],
                    style = $(this.refs['volume_' + name].getDOMNode()).attr('style');
                //$('.disk-visual .' + name + ', .volume-group-box-flag.' + name).attr('style', style + ' ' + this.volumeStylesTemplate(_.first(colors), _.last(colors)));
                $(this.refs['volume_' + name].getDOMNode()).attr('style', style + ' ' + this.volumeStylesTemplate(_.first(colors), _.last(colors)));
                $(this.refs['volume-group-box-flag_' + name].getDOMNode()).attr('style', this.volumeStylesTemplate(_.first(colors), _.last(colors)));
                

            }, this);
        },
        componentDidMount: function() {
            this.renderVisualGraph();
            this.applyColors();
        },
        render: function() {
            var disk = this.props.disk,
                volumes = this.props.volumes,
                diskMetaData = this.props.diskMetaData,
                locked = this.props.disabled,
                sortOrder = ['name', 'model', 'size'];
                
            return (
                <div className="disk-box disk" data-disk={disk.id}>

                    <div className="disk-box-name pull-left">{disk.get('name')} ({disk.id})</div>
                    <div className="disk-box-size pull-right">{i18n('cluster_page.nodes_tab.configure_disks.total_space')} : {utils.showDiskSize(disk.get('size'), 2)}</div>

                    <div className="disk-map-short disk-map-full" onClick={this.toggle.bind(this, this.props.index)}>
                        <div className="disk-map-image disk-visual">
                            {volumes &&_.map(volumes.models, function(volume) {
                                return (
                                    <div className={'volume-group ' + volume.get('name')} ref={'volume_' + volume.get('name')} style={{width: 0}}>
                                        <div className="toggle-volume">
                                            <div className="volume-group-name">{volume.get('label')}</div>
                                            <div className="volume-group-size">{utils.showDiskSize(0)}</div>
                                        </div>
                                        <div className="close-btn hide"></div>
                                    </div>
                                );
                            })}
                            <div className="volume-group unallocated" ref={'volume_unallocated'} style={{width: '100%'}}>
                                <div className="toggle-volume">
                                    <div className="volume-group-name">{i18n('cluster_page.nodes_tab.configure_disks.unallocated')}</div>
                                    <div className="volume-group-size">{utils.showDiskSize(disk.get('size'), 2)}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="disk-map-details disk-form collapse" ref={this.props.index}>
                        <div className="disk-info-box">
                            {diskMetaData &&
                                <div>
                                    <div className="disk-box-title">{i18n('cluster_page.nodes_tab.configure_disks.disk_information')}</div>
                                    {_.map(utils.sortEntryProperties(diskMetaData, sortOrder), function(propertyName) {
                                        return (
                                            <div className="disk-map-details-item enable-selection">
                                                <div className="disk-map-details-name">{propertyName.replace(/_/g, ' ')}</div>
                                                <div className="disk-map-details-parameter">{propertyName == 'size' ? utils.showDiskSize(diskMetaData[propertyName]) : diskMetaData[propertyName]}</div>
                                            </div>
                                        );
                                    })}
                                </div>
                            }
                        </div>

                        <div className="disk-utility-box">
                            <div className="disk-box-title">{i18n('cluster_page.nodes_tab.configure_disks.volume_groups')}</div>
                            {volumes &&_.map(volumes.models, function(volume) {
                                return (
                                    <div>
                                        <div className="volume-group-box volume-group" data-volume={volume.get('name')} >
                                            <div className="volume-group-box-flag" ref={'volume-group-box-flag_' + volume.get('name')}></div>
                                            <div className="volume-group-box-name">{volume.get('label')}</div>
                                            <div className="pull-right">
                                                {!locked &&
                                                    <div className="volume-group-box-edit"><span className="use-all-allowed" data-i18n="cluster_page.nodes_tab.configure_disks.use_all_allowed_space"></span></div>
                                                }
                                                <div className="volume-group-box-input">
                                                    <input id={disk.id + '-' + volume.get('name')} className="input-medium" type="text" name={volume.get('name')} value={disk.get('volumes').findWhere({name: volume.get('name')}).get('size') || 0 } onChange={this.tralala} />
                                                </div>
                                                <div className="volume-group-box-sizetype">{i18n('common.size.mb')}</div>
                                            </div>
                                        </div>
                                        <div className="volume-group-error-message enable-selection"></div>
                                    </div>
                                );
                            }, this)}
                            <div className="volume-group-error-message common enable-selection"></div>
                        </div>
                        <div className="clearfix"></div>
                    </div>
                  

                </div>

            );
        }
    });

    return EditNodeDisksScreen;
});
