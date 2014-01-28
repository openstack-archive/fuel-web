#    Copyright 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

require 'thread'

module Naily

  OVERHEAD_COST_TIME = 5 * 60 # sec

  class CancelSignal < Astute::StopSignal
    def initialize
      @queue = Hash.new([])
      @semaphore = Mutex.new
    end

    def stop_deploy?(task_id)
      @semaphore.synchronize do
        result = @queue.values.flatten.include?(task_id)
        clear_queue
        result
      end
    end

    def add_messages(messages)
      @semaphore.synchronize do
        @queue[Time.now.to_i] += messages.map { |m| m['args']['task_uuid'] }
        clear_queue_by_time
      end
    end

    private

    def clear_queue_by_time
      @queue.delete_if { |k, v| Time.now.to_i - k > Astute.config[:PROVISIONING_TIMEOUT] + OVERHEAD_COST_TIME }
    end

    def clear_queue
      @queue.clear
    end

  end
end