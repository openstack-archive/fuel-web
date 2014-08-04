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

    var input = {};

    var InputMixin = {
        getInitialState: function() {
            return {value: this.props.initialState};
        },
        onChange: function(e) {
            this.setState({value: e.target.type == 'checkbox' ? e.target.checked : e.target.value},
                _.bind(function() {
                    this.props.handleChange(this.props.name, this.state.value);
                }, this)
            );
        }
    };

    input.Checkbox = React.createClass({
        mixins: [InputMixin],
        render: function() {
            return (
                <div className={this.props.cs.common}>
                    <label className='parameter-box'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                <input
                                    type='checkbox'
                                    name={this.props.name}
                                    checked={this.state.value}
                                    disabled={this.props.disabled}
                                    onChange={this.onChange} />
                                <span>&nbsp;</span>
                            </div>
                        </div>
                        <div className={this.props.cs.label + ' parameter-name'}>{this.props.label}</div>
                        {this.props.description &&
                            <div className={this.props.cs.description + ' description'}>{this.props.description}</div>
                        }
                    </label>
                </div>
            );
        }
    });

    input.Dropdown = React.createClass({
        mixins: [InputMixin],
        render: function() {
            return (
                <div className={this.props.cs.common + ' parameter-box clearfix'}>
                    <div className={this.props.cs.label + ' parameter-name'}>{this.props.label}</div>
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
                    <div className={this.props.cs.description + ' description'}>{this.props.description}</div>
                </div>
            );
        }
    });

    input.RadioGroup = React.createClass({
        mixins: [InputMixin],
        render: function() {
            return (
                <div className={this.props.cs.common}>
                    <legend className={this.props.cs.label}>{this.props.label}</legend>
                    <form onChange={this.onChange}>
                        {_.map(this.props.values, function(value) {
                            if (!_.contains(this.props.hiddenValues, value.data)) {
                                return this.transferPropsTo(
                                    <input.RadioButton
                                        key={value.data}
                                        value={this.state.value}
                                        disabled={this.props.disabled || _.contains(this.props.disabledValues, value.data)} />
                                );
                            }
                        }, this)}
                    </form>
                </div>
            );
        }
    });

    input.RadioButton = React.createClass({
        render: function() {
            var option = _.find(this.props.values, {data: this.props.key});
            return (
                <label className='parameter-box clearfix'>
                    <div className='parameter-control'>
                        <div className='custom-tumbler'>
                            <input
                                type='radio'
                                name={this.props.name}
                                value={option.data}
                                defaultChecked={option.data == this.props.value}
                                disabled={this.props.disabled} />
                            <span>&nbsp;</span>
                        </div>
                    </div>
                    <div className='parameter-name'>{option.label}</div>
                    <div className={this.props.cs.description + ' description'}>{option.description}</div>
                </label>
            );
        }
    });

    input.TextField = React.createClass({
        mixins: [InputMixin],
        render: function() {
            var error = this.props.validate(this.props.name);
            return (
                <div className={this.props.cs.common + ' parameter-box clearfix'}>
                    <div className={this.props.cs.label + ' parameter-name'}>{this.props.label}</div>
                    <div className='parameter-control'>
                        <input
                            name={this.props.name}
                            className={error && 'error'}
                            type='text'
                            value={this.state.value}
                            disabled={this.props.disabled}
                            onChange={this.onChange} />
                    </div>
                    {error ?
                        <div className={this.props.cs.description + ' validation-error'}>{error}</div>
                        :
                        <div className={this.props.cs.description + ' description'}>{this.props.description}</div>
                    }
                </div>
            );
        }
    });

    input.PasswordField = React.createClass({
        mixins: [InputMixin],
        componentWillMount: function() {
            this.setState({visible: false});
        },
        togglePassword: function() {
            if (this.props.disabled) { return; }
            this.setState({visible: !this.state.visible});
        },
        render: function() {
            var error = this.props.validate(this.props.name);
            return (
                <div className={this.props.cs.common + ' parameter-box clearfix'}>
                    <div className={this.props.cs.label + ' parameter-name'}>{this.props.label}</div>
                    <div className='parameter-control input-append'>
                        <input
                            className={'input-append ' + (error && 'error')}
                            type={this.state.visible ? 'text' : 'password'}
                            name={this.props.name}
                            value={this.state.value}
                            disabled={this.props.disabled}
                            onChange={this.onChange} />
                        <span className='add-on' onClick={this.togglePassword}>
                            <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                        </span>
                    </div>
                    {error ?
                        <div className={this.props.cs.description + ' validation-error'}>{error}</div>
                        :
                        <div className={this.props.cs.description + ' description'}>{this.props.description}</div>
                    }
                </div>
            );
        }
    });

    return input;
});
