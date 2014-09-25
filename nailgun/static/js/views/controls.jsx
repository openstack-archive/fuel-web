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

    var controls = {},
        cx = React.addons.classSet;

    var InputMixin = {
        propTypes: {
            type: React.PropTypes.oneOf(['checkbox', 'radio', 'text', 'password', 'dropdown']).isRequired,
            name: React.PropTypes.string.isRequired,
            onChange: React.PropTypes.func.isRequired,
            value: React.PropTypes.oneOfType([
                React.PropTypes.string,
                React.PropTypes.number,
                React.PropTypes.bool
            ]),
            label: React.PropTypes.renderable,
            description: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable,
            validate: React.PropTypes.func,
            disabled: React.PropTypes.bool,
            cs: React.PropTypes.objectOf(React.PropTypes.object)
        },
        isRadioButton: function() {
            return this.props.key ? _.find(this.props.values, {data: this.props.key}) : null;
        },
        validate: function() {
            if (this.props.validate) return this.props.validate(this.props.name);
            return null;
        },
        onChange: function(e) {
            if (this.isRadioButton()) { return; }
            this.props.onChange(this.props.name, e.target.type == 'checkbox' ? e.target.checked : e.target.value);
        },
        renderInput: function(type) {
            type = type || this.props.type;
            var radioButton = this.isRadioButton();
            this.props.cs = this.props.cs || {};
            return (<input
                id={this.props.id}
                className={cx(_.extend({error: !_.isNull(this.validate())}, this.props.cs.input))}
                type={type}
                name={this.props.name}
                defaultValue={radioButton ? radioButton.data : this.props.value}
                defaultChecked={radioButton ? radioButton.data == this.props.value : this.props.value}
                disabled={this.props.disabled}
                onChange={this.onChange}
                maxLength={this.props.maxLength}
                onKeyDown={this.props.onKeyDown}
            />);
        },
        renderLabel: function() {
            var radioButton = this.isRadioButton(),
                labelClass = this.props.type == 'radio' && !radioButton ? this.props.cs.radioGrouplabel : this.props.cs.label;
            return (
                <div className={cx(_.extend({'enable-selection': true}, labelClass))}>
                    {radioButton ? radioButton.label : this.props.label}
                    {this.props.tooltipText &&
                        <controls.TooltipIcon tooltipText={this.props.tooltipText} />
                    }
                </div>
            );
        },
        renderDescription: function() {
            var error = this.validate(),
                radioButton = this.isRadioButton();
            return (
                <div className={cx(_.extend({'validation-error': !_.isNull(error), description: _.isNull(error)}, this.props.cs.description))}>
                    {!_.isNull(error) ? error : radioButton ? radioButton.description : this.props.description}
                </div>
            );
        }
    };

    controls.Checkbox = React.createClass({
        mixins: [InputMixin],
        propTypes: {
            controlOnly: React.PropTypes.bool
        },
        getDefaultProps: function() {
            return {type: 'checkbox'};
        },
        renderControl: function() {
            return (
                <div className='custom-tumbler'>
                    {this.renderInput()}
                    <span>&nbsp;</span>
                </div>
            );
        },
        render: function() {
            return (
                <div>
                    {this.props.controlOnly ?
                        this.renderControl()
                    :
                        (<div className={this.props.cs.common}>
                            <label className='parameter-box'>
                                <div className='parameter-control'>
                                    {this.renderControl()}
                                </div>
                                {this.renderLabel()}
                                {this.renderDescription()}
                            </label>
                        </div>)
                    }
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
                <div className={cx(_.extend({'select-all': true}, this.props.cs.common))}>
                    <label className={cx(this.props.cs.label)}>
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
        propTypes: {
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            hiddenValues: React.PropTypes.arrayOf(React.PropTypes.string),
            disabledValues: React.PropTypes.arrayOf(React.PropTypes.string)
        },
        getDefaultProps: function() {
            return {type: 'dropdown'};
        },
        render: function() {
            return (
                <div className={cx(_.extend({'parameter-box': true, clearfix: true}, this.props.cs.common))}>
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
        propTypes: {
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            hiddenValues: React.PropTypes.arrayOf(React.PropTypes.string),
            disabledValues: React.PropTypes.arrayOf(React.PropTypes.string),
            valueWarnings: React.PropTypes.object
        },
        render: function() {
            return (
                <div className={cx(this.props.cs.common)}>
                    {this.renderLabel()}
                    <form onChange={this.onChange}>
                        {_.map(this.props.values, function(value) {
                            if (!_.contains(this.props.hiddenValues, value.data)) {
                                return this.transferPropsTo(
                                    <controls.RadioButton
                                        key={value.data}
                                        value={this.props.value}
                                        disabled={this.props.disabled || _.contains(this.props.disabledValues, value.data)}
                                        tooltipText={this.props.valueWarnings[value.data].join(' ')}
                                    />
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
        propTypes: {
            key: React.PropTypes.string.isRequired
        },
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
                <div className={cx(_.extend({'parameter-box': true, clearfix: true}, this.props.cs.common))}>
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
        propTypes: {
            toggleable: React.PropTypes.bool
        },
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
                <div className={cx(_.extend({'parameter-box': true, clearfix: true}, this.props.cs.common))}>
                    {this.renderLabel()}
                    <div className={cx({'parameter-control': true, 'input-append': this.props.toggleable})}>
                        {this.renderInput(this.state.visible ? 'text' : 'password')}
                        {this.props.toggleable &&
                            <span className='add-on' onClick={this.togglePassword}>
                                <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                            </span>
                        }
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
            return (<i className='icon-attention text-warning' data-toggle='tooltip' title={this.props.tooltipText}></i>);
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
            var tableClasses = {
                table: true,
                'table-bordered': true,
                'table-striped': true
            };
            return (
                <table className={cx(_.extend(tableClasses, this.props.cs.table))}>
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
