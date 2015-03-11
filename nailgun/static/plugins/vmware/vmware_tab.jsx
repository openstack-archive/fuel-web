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
            _.defer(function() {dispatcher.trigger('vcenter_model_update'); });
        },
        render: function() {
            var metadata = this.props.metadata,
                options = this.props.options || [],
                errors = this.props.model.validationError,
                errorText = errors ? errors[metadata.name] : null;
            var classes = utils.classNames({
                'settings-group table-wrapper parameter-box': true,
                password: metadata.type == 'password',
                'has-error': !!errorText
            });
            return (
                <div key={metadata.name} className={classes}>
                    <controls.Input
                        key={metadata.name}
                        {... _.pick(metadata, 'name', 'type', 'label')}
                        value={this.props.model.get(metadata.name)}
                        checked={this.props.model.get(metadata.name)}
                        description={errorText || metadata.description}
                        descriptionClassName={utils.classNames({'validation-error': errorText})}
                        toggleable={metadata.type == 'password'}
                        wrapperClassName='tablerow-wrapper'
                        onChange={this.onChange}
                        disabled={this.props.disabled}
                    >
                        {options.map(function(index) {
                            return <option key={index.label} value={index.value}>{index.label}</option>;
                        }, this)}
                    </controls.Input>
                </div>
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
            var model = this.props.model;
            if (!model) {
                return null;
            }
            return (
                <div className={this.props.className}>
                    <legend className='vmware'>
                        {this.props.title}
                        {this.renderTooltipIcon()}
                    </legend>
                    <FieldGroup model={model} disabled={this.props.disabled}/>
                </div>
            );
        }
    });

    var NovaCompute = React.createClass({
        render: function() {
            var model = this.props.model;
            if (!model) {
                return null;
            }
            var removeButtonClasses = utils.classNames({'btn btn-link': true, hide: this.props.isRemovable});
            return (
                <div className='nova-compute'>
                    <h4>
                        <button className='btn btn-link'
                            disabled={this.props.disabled}
                            onClick={_.bind(function() {this.props.onAdd(model)}, this)}>
                            <i className='icon-plus-circle'></i>
                        </button>
                        <button className={removeButtonClasses}
                            disabled={this.props.disabled}
                            onClick={_.bind(function() {this.props.onRemove(model)}, this)}>
                            <i className='icon-minus-circle'></i>
                        </button>
                        &thinsp;
                        {i18n('vmware.nova_compute')}
                    </h4>
                    <FieldGroup model={model} disabled={this.props.disabled}/>
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
                isSingleInstance = (novaComputes.length == 1),
                disabled = actions.disable.cinder;

            return (
                <div className='idented'>
                    <legend className='vmware'>{i18n('vmware.nova_computes')}</legend>
                    {
                        novaComputes.map(function(value) {
                            return (
                                <NovaCompute
                                    key={value.cid}
                                    model={value}
                                    onAdd={this.addNovaCompute}
                                    onRemove={this.removeNovaCompute}
                                    isRemovable={isSingleInstance}
                                    disabled={disabled.result || this.props.disabled}
                                />
                            );
                        }, this)
                    }
                </div>
            );
        },
        renderCinder: function(actions) {
            var disabled = actions.disable.cinder;
            return (
                <GenericSection
                    model={this.props.model.get('cinder')}
                    className='cinder'
                    title={i18n('vmware.cinder')}
                    disabled={disabled.result || this.props.disabled}
                />
            );
        },
        render: function() {
            var restrictActions = this.props.model.testRestrictions();

            return (
                <div>
                    {this.renderFields(restrictActions)}
                    {this.renderComputes(restrictActions)}
                    {this.renderCinder(restrictActions)}
                </div>
            );
        }
    });

    var AvailabilityZones = React.createClass({
        mixins: [controls.tooltipMixin],
        render: function() {
            if (!this.props.collection) {
                return null;
            }
            return (
                <div className='availability-zones'>
                    <legend className='vmware'>
                        {i18n('vmware.availability_zones')}
                        {this.renderTooltipIcon()}
                    </legend>
                    {
                        this.props.collection.map(function(model) {
                            return <AvailabilityZone key={model.cid} model={model} disabled={this.props.disabled}/>;
                        }, this)
                    }
                </div>
            );
        }
    });

    var VCenter = React.createClass({
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
                <div className='vmware'>
                    <div className='wrapper'>
                        <h3>{i18n('vmware.title')}</h3>
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
                                className='network'
                                title={i18n('vmware.network')}
                                disabled={!editable || disable.network.result}
                                tooltipText={disable.network.message}
                            />
                        }
                        {!hide.glance.result &&
                            <GenericSection
                                model={model.get('glance')}
                                className='glance'
                                title={i18n('vmware.glance')}
                                disabled={!editable || disable.glance.result}
                                tooltipText={disable.glance.message}
                            />
                        }
                    </div>
                    <div className='page-control-box'>
                        <div className='page-control-button-placeholder'>
                            <button className='btn btn-load-defaults' onClick={this.onLoadDefaults} disabled={defaultsDisabled}>
                                {i18n('vmware.reset_to_defaults')}
                            </button>
                            <button className='btn btn-revert-changes' onClick={this.onCancel} disabled={!this.hasChanges}>
                                {i18n('vmware.cancel')}
                            </button>
                            <button className='btn btn-success btn-apply-changes' onClick={this.onSave} disabled={saveDisabled}>
                                {i18n('vmware.apply')}
                            </button>
                        </div>
                    </div>
                </div>
            );
        }
    });
    return VCenter;
});
