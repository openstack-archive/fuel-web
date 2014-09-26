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
    'jquery',
    'underscore',
    'react'
],
function($, _, React) {
    'use strict';

    var cx = React.addons.classSet;

    var Input = React.createClass({
        propTypes: {
            // props used by <input />
            type: React.PropTypes.string.isRequired,
            name: React.PropTypes.string,
            defaultValue: React.PropTypes.oneOfType([
                React.PropTypes.string,
                React.PropTypes.number,
                React.PropTypes.bool
            ]),
            defaultChecked: React.PropTypes.bool,
            disabled: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            onKeyDown: React.PropTypes.func,
            maxLength: React.PropTypes.renderable,
            // another props
            label: React.PropTypes.renderable,
            description: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable,
            error: React.PropTypes.renderable,
            toggleable: React.PropTypes.bool
        },
        getInitialState: function() {
            return {visible: false};
        },
        togglePassword: function() {
            if (this.props.disabled) return;
            this.setState({visible: !this.state.visible});
        },
        isCheckboxOrRadio: function() {
            return this.props.type === 'radio' || this.props.type === 'checkbox';
        },
        getValue: function() {
            var input = this.refs.input.getDOMNode();
            return this.isCheckboxOrRadio() ? input.checked : input.value;
        },
        componentDidMount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
        },
        componentWillUnmount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip('destroy');
        },
        renderInput: function() {
            var input = null;
            switch (this.props.type) {
                case 'select':
                    input = (<select ref='input' key='input'>{this.props.children}</select>);
                    break;
                case 'textarea':
                    input = <textarea ref='input' key='input' />;
                    break;
                default:
                    input = <input ref='input' key='input' />;
            }
            return this.isCheckboxOrRadio() ? [
                this.transferPropsTo(input),
                <span>&nbsp;</span>
            ] : this.transferPropsTo(input);
        },
        renderToggleablePasswordAddon: function() {
            return this.props.toggleable ? (
                <span key='add-on' className='add-on' onClick={this.togglePassword}>
                    <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                </span>
            ) : null;
        },
        renderTooltipIcon: function() {
            return this.props.tooltipText ? (
                <i key='tooltip' ref='tooltip' className='icon-attention text-warning' data-toggle='tooltip' title={this.props.tooltipText} />
            ) : null;
        },
        renderLabel: function(children) {
            var classes = {
                'enable-selection': true,
                'input-append': this.props.toggleable
            };
            return this.props.label ? (
                <label key='label' className={cx(classes)} htmlFor={this.props.id}>
                    {this.props.label}
                    {children}
                </label>
            ) : children;
        },
        renderDescription: function() {
            var error = !_.isNull(this.props.error);
            return error || this.props.description ? (
                <div key='description' className='description enable-selection'>
                    {error ? this.props.error : this.props.description}
                </div>
            ) : null;
        },
        renderWrapper: function(children) {
            var classes = {
                'control-box': true,
                'has-error': !_.isNull(this.props.error)
            };
            classes[this.props.commonClassName] = this.props.commonClassName;
            return (<div className={cx(classes)}>{children}</div>);
        },
        render: function() {
            return this.renderWrapper([
                this.renderLabel([
                    this.renderInput(),
                    this.renderToggleablePasswordAddon(),
                    this.renderTooltipIcon()
                ]),
                this.renderDescriprion()
            ]);
        }
    });

    return Input;
});
