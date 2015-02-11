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
    'react',
    'jquery',
    'i18n',
    'underscore',
    'dispatcher',
    'utils',
    'jsx!views/controls',
    'jsx!component_mixins',
    'plugins/vmware/vmware_models'
], function(React, $, i18n, _, dispatcher, utils, controls, componentMixins, vmwareModels) {
    'use strict';

    var Field = React.createClass({
        mixins: [controls.tooltipMixin],
        onChange: function(name, value) {
            this.props.model.set(name, value);
            this.setState({model: this.props.model});
            _.defer(function() {dispatcher.trigger('vcenter_model_update');});
        },
        render: function() {
            var metadata = this.props.metadata,
                value = this.props.model.get(metadata.name);
            return (
                <controls.Input
                    {... _.pick(metadata, 'name', 'type', 'label', 'description')}
                    value={value}
                    checked={value}
                    toggleable={metadata.type == 'password'}
                    onChange={this.onChange}
                    disabled={this.props.disabled}
                    error={(this.props.model.validationError || {})[metadata.name]}
                >
                    {this.props.options && this.props.options.map(function(index) {
                        return <option key={index.label} value={index.value}>{index.label}</option>;
                    })}
                </controls.Input>
            );
        }
    });

    var FieldGroup = React.createClass({
        render: function() {
            var restrictions = this.props.model.testRestrictions();
            var metadata = _.filter(this.props.model.get('metadata'), vmwareModels.isRegularField);
            var fields = metadata.map(function(meta) {
                return (
                    <Field
                        key={meta.name}
                        model={this.props.model}
                        metadata={meta}
                        disabled={this.props.disabled}
                        disableWarning={restrictions.disable[meta.name]}/>
                );
            }, this);
            return (
                <div>
                    {fields}
                </div>
            );
        }
    });

    var GenericSection = React.createClass({
        mixins: [controls.tooltipMixin],
        render: function() {
            if (!this.props.model) return null;
            return (
                <div className='col-xs-12 forms-box'>
                    <h3>
                        {this.props.title}
                        {this.renderTooltipIcon()}
                    </h3>
                    <FieldGroup model={this.props.model} disabled={this.props.disabled}/>
                </div>
            );
        }
    });

    var NovaCompute = React.createClass({
        render: function() {
            if (!this.props.model) return null;
            return (
                <div className='nova-compute'>
                    <h4>
                        <div className='btn-group'>
                            <button
                                className='btn btn-link'
                                disabled={this.props.disabled}
                                onClick={_.bind(function() {this.props.onAdd(this.props.model)}, this)}
                            >
                                <i className='glyphicon glyphicon-plus-sign' />
                            </button>
                            {!this.props.isRemovable &&
                                <button
                                    className='btn btn-link'
                                    disabled={this.props.disabled}
                                    onClick={_.bind(function() {this.props.onRemove(this.props.model)}, this)}
                                >
                                    <i className='glyphicon glyphicon-minus-sign' />
                                </button>
                            }
                        </div>
                        {i18n('vmware.nova_compute')}
                    </h4>
                    <FieldGroup model={this.props.model} disabled={this.props.disabled}/>
                </div>
            );
        }
    });

    var AvailabilityZone = React.createClass({
        addNovaCompute: function(current) {
            var collection = this.props.model.get('nova_computes'),
                index = collection.indexOf(current);
            collection.add(current.clone(), {at: index + 1});
            collection.parseRestrictions();
            this.setState({model: this.props.model});
            _.defer(function() {dispatcher.trigger('vcenter_model_update'); });
        },
        removeNovaCompute: function(current) {
            var collection = this.props.model.get('nova_computes');
            collection.remove(current);
            this.setState({model: this.props.model});
            _.defer(function() { dispatcher.trigger('vcenter_model_update'); });
        },
        renderFields: function() {
            var model = this.props.model,
                meta = model.get('metadata');
            meta = _.filter(meta, vmwareModels.isRegularField);
            return (
                <FieldGroup model={model} disabled={this.props.disabled}/>
            );
        },
        renderComputes: function(actions) {
            var novaComputes = this.props.model.get('nova_computes'),
                isSingleInstance = novaComputes.length == 1,
                disabled = actions.disable.nova_computes;

            return (
                <div className='col-xs-offset-1'>
                    <h3>
                        {i18n('vmware.nova_computes')}
                    </h3>
                    {novaComputes.map(function(compute) {
                        return (
                            <NovaCompute
                                key={compute.cid}
                                model={compute}
                                onAdd={this.addNovaCompute}
                                onRemove={this.removeNovaCompute}
                                isRemovable={isSingleInstance}
                                disabled={disabled.result || this.props.disabled}
                            />
                        );
                    }, this)}
                </div>
            );
        },
        render: function() {
            var restrictActions = this.props.model.testRestrictions();

            return (
                <div>
                    {this.renderFields(restrictActions)}
                    {this.renderComputes(restrictActions)}
                </div>
            );
        }
    });

    var AvailabilityZones = React.createClass({
        mixins: [controls.tooltipMixin],
        render: function() {
            if (!this.props.collection) return null;
            return (
                <div className='col-xs-12 forms-box'>
                    <h3>
                        {i18n('vmware.availability_zones')}
                        {this.renderTooltipIcon()}
                    </h3>
                    {this.props.collection.map(function(model) {
                        return <AvailabilityZone key={model.cid} model={model} disabled={this.props.disabled}/>;
                    }, this)}
                </div>
            );
        }
    });

    var VCenter = React.createClass({
        statics: {
            isVisible: function(cluster) {
                return cluster.get('settings').get('common.use_vcenter').value;
            }
        },
        componentDidMount: function() {
            this.clusterId = this.props.cluster.id;
            this.model = this.props.cluster.get('vcenter');
            this.model.on('sync', function() {
                this.model.parseRestrictions();
                this.actions = this.model.testRestrictions();
                if (!this.model.loadDefaults) {
                    this.json = JSON.stringify(this.model.toJSON());
                }
                this.model.loadDefaults = false;
                this.setState({model: this.model});
            }, this);
            this.defaultModel = new vmwareModels.VCenter({id: this.clusterId});
            this.defaultModel.on('sync', function() {
                this.defaultModel.parseRestrictions();
                this.defaultsJson = JSON.stringify(this.defaultModel.toJSON());
                this.setState({defaultModel: this.defaultModel});
            }, this);
            this.setState({model: this.model, defaultModel: this.defaultModel});

            this.model.setModels({
                cluster: this.props.cluster,
                settings: this.props.cluster.get('settings'),
                networking_parameters: this.props.cluster.get('networkConfiguration').get('networking_parameters')
            });

            this.readDefaultsData();
            this.readData();
            dispatcher.on('vcenter_model_update', _.bind(function() {
                if (this.isMounted()) {
                    this.forceUpdate();
                }
            }, this));
        },
        componentWillUnmount: function() {
            this.defaultModel.off('sync', null, this);
            this.model.off('sync', null, this);
            dispatcher.off('vcenter_model_update');
        },
        getInitialState: function() {
            return {model: null};
        },
        readData: function() {
            this.model.fetch();
        },
        readDefaultsData: function() {
            this.defaultModel.loadDefaults = true;
            this.defaultModel.fetch();
        },
        saveData: function() {
            this.model.save();
        },
        onLoadDefaults: function() {
            this.model.loadDefaults = true;
            this.model.fetch().done(_.bind(function() {
                this.model.loadDefaults = false;
            }, this));
        },
        onCancel: function() {
            this.readData();
        },
        onSave: function() {
            this.saveData();
        },
        revertChanges: function() {
            this.readData();
        },
        render: function() {
            if (!this.state.model || !this.actions) {
                return null;
            }

            var model = this.state.model,
                currentJson = JSON.stringify(this.model.toJSON()),
                editable = this.props.cluster.isAvailableForSettingsChanges(),
                hide = this.actions.hide || {},
                disable = this.actions.disable || {};

            model.isValid();
            this.hasChanges = (this.json != currentJson);
            this.hasDefaultsChanges = (this.defaultsJson != currentJson);
            var saveDisabled = !editable || !this.hasChanges || !!model.validationError,
                defaultsDisabled = !editable || !this.hasDefaultsChanges;

            return (
                <div className='row'>
                    <div className='title'>{i18n('vmware.title')}</div>
                    {!hide.availability_zones.result &&
                        <AvailabilityZones
                            collection={model.get('availability_zones')}
                            disabled={!editable || disable.availability_zones.result}
                            tooltipText={disable.availability_zones.message}
                        />
                    }
                    {!hide.network.result &&
                        <GenericSection
                            model={model.get('network')}
                            title={i18n('vmware.network')}
                            disabled={!editable || disable.network.result}
                            tooltipText={disable.network.message}
                        />
                    }
                    {!hide.glance.result &&
                        <GenericSection
                            model={model.get('glance')}
                            title={i18n('vmware.glance')}
                            disabled={!editable || disable.glance.result}
                            tooltipText={disable.glance.message}
                        />
                    }
                    <div className='col-xs-12 page-buttons content-elements'>
                        <div className='well clearfix'>
                            <div className='btn-group pull-right'>
                                <button className='btn btn-default btn-load-defaults' onClick={this.onLoadDefaults} disabled={defaultsDisabled}>
                                    {i18n('vmware.reset_to_defaults')}
                                </button>
                                <button className='btn btn-default btn-revert-changes' onClick={this.onCancel} disabled={!this.hasChanges}>
                                    {i18n('vmware.cancel')}
                                </button>
                                <button className='btn btn-success btn-apply-changes' onClick={this.onSave} disabled={saveDisabled}>
                                    {i18n('vmware.apply')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });
    return VCenter;
});
