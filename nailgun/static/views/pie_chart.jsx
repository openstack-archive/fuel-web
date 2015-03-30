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
        'underscore',
        'i18n',
        'react',
        'utils',
        'models',
        'dispatcher',
        'd3'
    ],
    function(_, i18n, React, utils, models, dispatcher, d3) {
        'use strict';

    var data = [2704659, 4499890, 2159981, 3853788, 14106543, 8819342, 612463];

    var Chart = React.createClass({
        render: function() {
            return (
                <svg width={this.props.width} height={this.props.height}>{this.props.children}</svg>
            );
        }
    });

    var Sector = React.createClass({
        render: function() {
            var arc = d3.svg.arc()
                .outerRadius(240)
                .innerRadius(200);
            return (
                <g className="arc">
                    <path d={arc(this.props.data)}></path>
                </g>
            );
        }
    });

    var DataSeries = React.createClass({
        render: function() {

            var pie = d3.layout.pie()
            var bars = _.map(pie(this.props.data), function(point, i) {
                return (
                    <Sector data={point} key={i}/>
                )
            });

            return (
                <g transform="translate(480, 250)">{bars}</g>
            );
        }
    });

    var PieChart = React.createClass({
        getDefaultProps: function() {
            return {
                width: 200,
                height: 200
            };
        },
        render: function() {

            return (
                <Chart width={this.props.width} height={this.props.height}>
                    <DataSeries data={data} width={this.props.width} height={this.props.height}  />
                </Chart>
            );
        }
    });

    return PieChart;

});
