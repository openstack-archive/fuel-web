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
define(['jquery', 'underscore', 'react'], function($, _, React) {
    'use strict';

    var controls = {};

    var InputMixin = {
        getInitialState: function() {
            return {value: this.props.value};
        },
        onChange: function(e) {
            if (this.props.type == 'radio') { return; }
            this.setState({value: e.target.type == 'checkbox' ? e.target.checked : e.target.value},
                _.bind(function() {
                    this.props.handleChange(this.props.name, this.state.value);
                }, this)
            );
        },
        getOption: function(key) {
            return _.find(this.props.values, {data: key});
        },
        getError: function() {
            return _.contains(['text', 'password'], this.props.type) && this.props.validate(this.props.name);
        },
        renderInput: function(key) {
            var type = this.props.type;
            return (<input
                className={(type == 'password' && 'input-append') + (this.getError() && ' error')}
                type={type == 'password' ? this.state.visible ? 'text' : 'password' : type}
                name={this.props.name}
                value={this.state.value}
                disabled={this.props.disabled}
                defaultChecked={type == 'radio' ? this.getOption(key).data == this.props.value : this.props.value}
                onChange={this.onChange} />);
        },
        renderLabel: function(className, label) {
            label = label || this.props.label;
            className = className || 'parameter-name ' + this.props.cs.label;
            return (
                <div className={className}>
                    {label}
                    {this.props.warnings.length &&
                        <controls.TooltipIcon warnings={this.props.warnings} />
                    }
                </div>
            );
        },
        renderDescription: function(key) {
            var error = this.getError();
            return error ?
                (<div className={this.props.cs.description + ' validation-error'}>{error}</div>)
                :
                (<div className={this.props.cs.description + ' description'}>
                    {this.props.type == 'radio' ? this.getOption(key).description : this.props.description}
                </div>);
        }
    };

    controls.Checkbox = React.createClass({
        mixins: [InputMixin],
        render: function() {
            return (
                <div className={this.props.cs.common}>
                    <label className='parameter-box'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                {this.renderInput()}
                                <span>&nbsp;</span>
                            </div>
                        </div>
                        {this.renderLabel()}
                        {this.renderDescription()}
                    </label>
                </div>
            );
        }
    });

    controls.Dropdown = React.createClass({
        mixins: [InputMixin],
        render: function() {
            return (
                <div className={this.props.cs.common + ' parameter-box clearfix'}>
                    {this.renderLabel()}
                    <div className='parameter-control'>
                        <select
                            name={this.props.name}
                            value={this.state.value}
                            disabled={this.props.disabled}
                            onChange={this.onChange}
                        >
                            {_.map(this.props.values, function(value) {
                                if (!_.contains(this.props.hiddenValues, value.data)) {
                                    return <option key={value.data} value={value.data} disabled={_.contains(this.props.disabledValues, value.data)}>{value.label}</option>;
                                }
                            }, this)}
                        </select>
                    </div>
                    {this.renderDescription()}
                </div>
            );
        }
    });

    controls.RadioGroup = React.createClass({
        mixins: [InputMixin],
        render: function() {
            return (
                <div className={this.props.cs.common}>
                    {this.renderLabel(this.props.cs.label)}
                    <form onChange={this.onChange}>
                        {_.map(this.props.values, function(value) {
                            if (!_.contains(this.props.hiddenValues, value.data)) {
                                return this.transferPropsTo(
                                    <controls.RadioButton
                                        key={value.data}
                                        value={this.state.value}
                                        disabled={this.props.disabled || _.contains(this.props.disabledValues, value.data)}
                                        warnings={this.props.valueWarnings[value.data]}
                                        renderInput={_.bind(this.renderInput, this)}
                                        renderLabel={_.bind(this.renderLabel, this, 'parameter-name', value.label)}
                                        renderDescription={_.bind(this.renderDescription, this)} />
                                );
                            }
                        }, this)}
                    </form>
                </div>
            );
        }
    });

    controls.RadioButton = React.createClass({
        render: function() {
            var option = _.find(this.props.values, {data: this.props.key});
            return (
                <label className='parameter-box clearfix'>
                    <div className='parameter-control'>
                        <div className='custom-tumbler'>
                            {this.props.renderInput(this.props.key)}
                            <span>&nbsp;</span>
                        </div>
                    </div>
                    {this.props.renderLabel()}
                    {this.props.renderDescription(this.props.key)}
                </label>
            );
        }
    });

    controls.TextField = React.createClass({
        mixins: [InputMixin],
        render: function() {
            return (
                <div className={this.props.cs.common + ' parameter-box clearfix'}>
                    {this.renderLabel()}
                    <div className='parameter-control'>
                        {this.renderInput()}
                    </div>
                    {this.renderDescription()}
                </div>
            );
        }
    });

    controls.PasswordField = React.createClass({
        mixins: [InputMixin],
        componentWillMount: function() {
            this.setState({visible: false});
        },
        togglePassword: function() {
            if (this.props.disabled) { return; }
            this.setState({visible: !this.state.visible});
        },
        render: function() {
            return (
                <div className={this.props.cs.common + ' parameter-box clearfix'}>
                    {this.renderLabel()}
                    <div className='parameter-control input-append'>
                        {this.renderInput()}
                        <span className='add-on' onClick={this.togglePassword}>
                            <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                        </span>
                    </div>
                    {this.renderDescription()}
                </div>
            );
        }
    });

    controls.TooltipIcon = React.createClass({
        componentDidMount: function() {
            this.getDOMNode().tooltip();
        },
        componentWillUnmount: function() {
            this.getDOMNode().tooltip('destroy');
        },
        render: function() {
            return (<i className='icon-attention text-warning' data-toggle='tooltip' title={this.props.warnings.join(' ')}></i>);
        }
    });

    controls.ProgressBar = React.createClass({
        render: function() {
            return (
               <div className='progress-bar'>
                    <div className='progress progress-striped progress-success active'>
                        <div className='bar'/>
                    </div>
                </div>
            );
        }
    });

    return controls;
});
