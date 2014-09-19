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
            return {value: this.getValue()};
        },
        isRadioButton: function() {
            return this.props.key ? _.find(this.props.values, {data: this.props.key}) : null;
        },
        getValue: function() {
            var radioButton = this.isRadioButton();
            return radioButton ? radioButton.data : this.props.value;
        },
        getError: function() {
            return this.props.validate && this.props.validate(this.props.name);
        },
        onChange: function(e) {
            if (this.isRadioButton()) { return; }
            this.props.onChange(this.props.name, e.target.type == 'checkbox' ? e.target.checked : e.target.value);
        },
        renderInput: function(type) {
            type = type || this.props.type;
            var radioButton = this.isRadioButton();
            return (<input
                className={this.getError() && 'error'}
                type={type}
                name={this.props.name}
                value={this.getValue()}
                checked={radioButton ? radioButton.data == this.props.value : this.props.value}
                disabled={this.props.disabled}
                onChange={this.onChange} />);
        },
        renderLabel: function() {
            var radioButton = this.isRadioButton(),
                labelClass = this.props.type == 'radio' && !radioButton ? this.props.cs.radioGrouplabel : this.props.cs.label;
            return (
                <div className={labelClass + ' enable-selection'}>
                    {radioButton ? radioButton.label : this.props.label}
                    {!!this.props.warnings.length &&
                        <controls.TooltipIcon warnings={this.props.warnings} />
                    }
                </div>
            );
        },
        renderDescription: function() {
            var error = this.getError(),
                radioButton = this.isRadioButton();
            return error ?
                (<div className={this.props.cs.description + ' validation-error'}>{error}</div>)
                :
                (<div className={this.props.cs.description + ' description'}>
                    {radioButton ? radioButton.description : this.props.description}
                </div>);
        }
    };

    controls.Checkbox = React.createClass({
        mixins: [InputMixin],
        getDefaultProps: function() {
            return {type: 'checkbox'};
        },
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

    controls.SelectAllCheckbox = React.createClass({
        mixins: [InputMixin],
        getDefaultProps: function() {
            return {type: 'checkbox'};
        },
        render: function() {
            return (
                <div className={this.props.cs.common}>
                    <label className={this.props.cs.label}>
                        {this.renderInput()}
                        <span>&nbsp;</span>
                        <span>{$.t('common.select_all_button')}</span>
                    </label>
                </div>
            );
        }
    });

    controls.Dropdown = React.createClass({
        mixins: [InputMixin],
        getDefaultProps: function() {
            return {type: 'dropdown'};
        },
        render: function() {
            return (
                <div className={this.props.cs.common + ' parameter-box clearfix'}>
                    {this.renderLabel()}
                    <div className='parameter-control'>
                        <select
                            name={this.props.name}
                            defaultValue={this.props.value}
                            disabled={this.props.disabled}
                            onChange={this.onChange}
                        >
                            {_.map(this.props.values, function(value) {
                                if (!_.contains(this.props.hiddenValues, value.data)) {
                                    return <option
                                        key={value.data}
                                        value={value.data}
                                        disabled={_.contains(this.props.disabledValues, value.data)}
                                    >
                                        {value.label}
                                    </option>;
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
                    {this.renderLabel()}
                    <form onChange={this.onChange}>
                        {_.map(this.props.values, function(value) {
                            if (!_.contains(this.props.hiddenValues, value.data)) {
                                return this.transferPropsTo(
                                    <controls.RadioButton
                                        key={value.data}
                                        value={this.props.value}
                                        disabled={this.props.disabled || _.contains(this.props.disabledValues, value.data)}
                                        warnings={this.props.valueWarnings[value.data]} />
                                );
                            }
                        }, this)}
                    </form>
                </div>
            );
        }
    });

    controls.RadioButton = React.createClass({
        mixins: [InputMixin],
        getDefaultProps: function() {
            return {type: 'radio'};
        },
        render: function() {
            return (
                <label className='parameter-box clearfix'>
                    <div className='parameter-control'>
                        <div className='custom-tumbler'>
                            {this.renderInput()}
                            <span>&nbsp;</span>
                        </div>
                    </div>
                    {this.renderLabel()}
                    {this.renderDescription()}
                </label>
            );
        }
    });

    controls.TextField = React.createClass({
        mixins: [InputMixin],
        getDefaultProps: function() {
            return {type: 'text'};
        },
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
        getInitialState: function() {
            return {visible: false};
        },
        getDefaultProps: function() {
            return {type: 'password'};
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
                        {this.renderInput(this.state.visible ? 'text' : 'password')}
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
            $(this.getDOMNode()).tooltip();
        },
        componentWillUnmount: function() {
            $(this.getDOMNode()).tooltip('destroy');
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

    controls.Table = React.createClass({
        render: function() {
            var tableClass = 'table table-bordered table-striped ' + this.props.className;
            return (
                <table className={tableClass}>
                    <thead>
                        <tr>
                            {_.map(this.props.head, function(column, index) {
                                return <th key={index} className={column.className || ''}>{column.label}</th>;
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {_.map(this.props.body, function(row, rowIndex) {
                            return <tr key={rowIndex}>
                                {_.map(row, function(column, columnIndex) {
                                    return <td key={columnIndex} className='enable-selection'>{column}</td>;
                                })}
                            </tr>;
                        })}
                    </tbody>
                </table>
            );
        }
    });

    return controls;
});
