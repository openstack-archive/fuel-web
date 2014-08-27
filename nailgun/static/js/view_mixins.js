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
define([], function() {
    'use strict';

    return {
        toggleablePassword: {
            events: {
                'click span.add-on': 'togglePassword'
            },
            togglePassword: function(e) {
                var input = this.$(e.currentTarget).prev();
                if (input.attr('disabled')) {return;}
                input.attr('type', input.attr('type') == 'text' ? 'password' : 'text');
                this.$(e.currentTarget).find('i').toggleClass('hide');
            },
            render: function() {
                this.$('input[type=password]:not(.no-show)').each(function() {
                    $(this)
                        .after('<span class="add-on"><i class="icon-eye"/><i class="icon-eye-off hide"/></span>')
                        .addClass('input-append')
                        .parent('.parameter-control').addClass('input-append');
                });
            }
        }
    };
});
