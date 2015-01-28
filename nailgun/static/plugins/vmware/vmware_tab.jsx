/*
 * Copyright 2014 Mirantis, Inc.
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
    'underscore',
    'jsx!views/controls',
    'jsx!component_mixins',
    'plugins/vmware/vmware_models'
], function(React, $, _, controls, componentMixins, VmwareModels) {
    'use strict';

    var cx = React.addons.classSet;

    function isRegularField(field) {
        return field.type == 'text' || field.type == 'password' || field.type == 'checkbox';
    }

    var Field = React.createClass({
        onChange: function(name, value) {
            this.props.model.set(name, value);
            this.setState({model: this.props.model});
            _.defer(function() { $(document).trigger('vmware'); });
        },
        render: function() {
            //var key = this.props.key;
            var metadata = this.props.metadata,
                options = this.props.options || [],
                errors = this.props.model.validationError,
                errorText = errors ? errors[metadata.name] : null;
            var classes = cx({
                'settings-group': true,
                'table-wrapper': true,
                'parameter-box': true,
                password: metadata.type == 'password',
                'has-error': (errorText ? true : false)
            });
            return (
                <div key={metadata.name} className={classes}>
                    <controls.Input
                        key={metadata.name}
                        name={metadata.name}
                        type={metadata.type || 'text'}
                        label={metadata.label}
                        value={this.props.model.get(metadata.name)}
                        checked={this.props.model.get(metadata.name)}
                        description={errorText || metadata.description}
                        descriptionClassName={errorText ? 'validation-error' : null}
                        toggleable={metadata.type == 'password' ? true : false}
                        wrapperClassName="tablerow-wrapper"
                        onChange={this.onChange}
                        disabled={ this.props.isNew ? false : metadata.lockOnEdit }
                    >
                        {options.map(function(index) {
                            return <option key={Math.random()} value={index.value}>{index.label}</option>;
                        }, this)}
                    </controls.Input>
                </div>
            );
        }
    });

    var FieldGroup = React.createClass({
        render: function() {
            var metadata = _.filter(this.props.model.get('metadata'), isRegularField);
            var fields = metadata.map(function(meta, index) {
                return (
                    <Field metadata={metadata[index]} model={this.props.model}/>
                );
            }, this);
            return (
                <div>
                    {fields}
                </div>
            );
        }
    });

    var Cinder = React.createClass({
        render: function() {
            var model = this.props.model;
            if (!model) {
                return false;
            }
            return (
                <div className="cinder">
                    <legend className="vmware">{$.t('vmware.cinder')}</legend>
                    <FieldGroup model={model}/>
                </div>
            );
        }
    });

    var NovaCompute = React.createClass({
        render: function() {
            var model = this.props.model;
            if (!model) {
                return false;
            }
            var removeButtonStyle = this.props.isRemovable ? {display: 'none'} : {};
            return (
                <div className="nova-compute">
                    <h4>
                        <button className="btn btn-link"
                            onClick={_.bind(function() {this.props.onAdd(model)}, this)}>
                            <i className="icon-plus-circle"></i>
                        </button>
                        <button className="btn btn-link"
                            onClick={_.bind(function() {this.props.onRemove(model)}, this)}
                            style={removeButtonStyle}>
                            <i className="icon-minus-circle"></i>
                        </button>
                        &thinsp;
                        Compute Instance
                    </h4>
                    <FieldGroup model={model}/>
                </div>
            );
        }
    });

    var AvailabilityZone = React.createClass({
        addNovaCompute: function(current) {
            var collection = this.props.model.get('nova_computes'),
                index = collection.indexOf(current);

            collection.add(current.clone(), {at: index + 1});
            this.setState({model: this.props.model});
            _.defer(function() { $(document).trigger('vmware'); });
        },
        removeNovaCompute: function(current) {
            var collection = this.props.model.get('nova_computes');
            collection.remove(current);
            this.setState({model: this.props.model});
            _.defer(function() { $(document).trigger('vmware'); });
        },
        renderFields: function() {
            var model = this.props.model,
                meta = this.props.model.get('metadata');
            meta = _.filter(meta, isRegularField);
            return (
                <FieldGroup model={model}/>
            );
        },
        renderComputes: function() {
            var novaComputes = this.props.model.get('nova_computes'),
                isSingleInstance = (novaComputes.length == 1);
            return (
                <div className="idented">
                    <legend className="vmware">{$.t('vmware.nova_computes')}</legend>
                    {
                        novaComputes.map(function(value) {
                            return (
                                <NovaCompute
                                    model={value}
                                    onAdd={this.addNovaCompute}
                                    onRemove={this.removeNovaCompute}
                                    isRemovable={isSingleInstance}
                                />
                            );
                        }, this)
                    }
                </div>
            );
        },
        renderCinder: function() {
            return (
                <Cinder  model={this.props.model.get('cinder')}/>
            );
        },
        render: function() {
            return (
                <div>
                    {this.renderFields()}
                    {this.renderComputes()}
                    {this.renderCinder()}
                </div>
            );
        }
    });

    var AvailabilityZones = React.createClass({
        renderInstance: function(model) {
            return (<AvailabilityZone model={model}/>);
        },
        render: function() {
            if (!this.props.collection) {
                return false;
            }
            return (
                <div className="availability-zones">
                    <legend className="vmware">{$.t('vmware.availability_zones')}</legend>
                    {
                        this.props.collection.map(function(model) {
                            return <AvailabilityZone model={model}/>;
                        })
                    }
                </div>
            );
        }
    });

    var Network = React.createClass({
        render: function() {
            var model = this.props.model;
            if (!model) {
                return false;
            }
            return (
                <div className="network">
                    <legend className="vmware">{$.t('vmware.network')}</legend>
                    <FieldGroup meta={model.get('metadata')} model={model}/>
                </div>
            );
        }
    });

    var Glance = React.createClass({
        render: function() {
            var model = this.props.model;
            if (!model) {
                return false;
            }
            return (
                <div className="glance">
                    <legend className="vmware">{$.t('vmware.glance')}</legend>
                    <FieldGroup meta={model.get('metadata')} model={model}/>
                </div>
            );
        }
    });

    var VCenter = React.createClass({
        componentWillMount: function() {
            this.clusterId = this.props.cluster.id;
            this.model = new VmwareModels.VCenter({id: this.clusterId});
            this.defaultModel = new VmwareModels.VCenter({id: this.clusterId});
            this.setState({model: this.model, defaultModel: this.defaultModel});

            this.readDefaultsData();
            this.readData();
            $(document).on('vmware', _.bind(function() {this.forceUpdate()}, this));
        },
        componentWillUnmount: function() {
            $(document).off('vmware');
        },
        readData: function() {
            this.model.fetch().done(_.bind(function() {
                this.json = JSON.stringify(this.model.toJSON());
                this.setState({model: this.model});
            }, this));
        },
        readDefaultsData: function() {
            this.defaultModel.loadDefaults = true;
            this.defaultModel.fetch().done(_.bind(function() {
                this.defaultsJson = JSON.stringify(this.defaultModel.toJSON());
                this.setState({defaultModel: this.defaultModel});
            }, this));
        },
        saveData: function() {
            this.model.save().done(
                _.bind(function() {
                    this.json = JSON.stringify(this.model.toJSON());
                    this.setState({model: this.model});
                }, this));
        },
        onLoadDefaults: function() {
            this.model.loadDefaults = true;
            this.model.fetch().done(_.bind(function() {
                this.model.loadDefaults = false;
                this.defaultsJson = JSON.stringify(this.model.toJSON());
                this.setState({mode: this.model});
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
            var model = this.state.model,
                currentJson = JSON.stringify(this.model.toJSON());
            this.hasChanges = (this.json != currentJson);
            this.hasDefaultsChanges = (this.defaultsJson != currentJson);

            model.isValid();
            var saveDisabled = !this.hasChanges || !!model.validationError;
            var defaultsDisabled = !this.hasDefaultsChanges;

            return (
                <div className="vmware">
                    <div className="wrapper">
                        <h3>{$.t('vmware.title')}</h3>
                        <AvailabilityZones collection={model.get('availability_zones')}/>
                        <Network model={model.get('network')}/>
                        <Glance  model={model.get('glance')}/>
                    </div>
                    <div className="page-control-box">
                        <div className="page-control-button-placeholder">
                            <button className="btn btn-load-defaults" onClick={this.onLoadDefaults} disabled={defaultsDisabled}>
                                {$.t('vmware.reset_to_defaults')}
                            </button>
                            <button className="btn btn-revert-changes"  onClick={this.onCancel} disabled={saveDisabled}>
                                {$.t('vmware.cancel')}
                            </button>
                            <button className="btn btn-success btn-apply-changes" onClick={this.onSave} disabled={saveDisabled}>
                                {$.t('vmware.apply')}
                            </button>
                        </div>
                    </div>
                </div>

            );
        }
    });
    return VCenter;
});
