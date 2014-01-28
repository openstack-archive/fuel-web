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

require 'json'
require 'naily/cancel_signal'

module Naily
  class Server
    def initialize(channel, exchange, delegate, producer, cancel_channel, cancel_exchange)
      @channel  = channel
      @exchange = exchange
      @delegate = delegate
      @producer = producer
      @cancel_channel = cancel_channel
      @cancel_exchange = cancel_exchange
      @cancel_signal = CancelSignal.new
    end

    def run
      @queue = @channel.queue(Naily.config.broker_queue, :durable => true)
      @queue.bind @exchange, :routing_key => Naily.config.broker_queue

      @cancel_queue = @cancel_channel.queue("", :exclusive => true, :auto_delete => true).bind(@cancel_exchange)

      @loop = Thread.new(&method(:server_loop))
      self
    end

  private

    def server_loop
      consume_two
      loop do
        consume_one do |payload|
          dispatch payload
        end
        Thread.stop
      end
    end

    def consume_one
      @consumer = AMQP::Consumer.new(@channel, @queue)
      @consumer.on_delivery do |metadata, payload|
        metadata.ack
        Thread.new do
          yield payload
          @loop.wakeup
        end
        @consumer.cancel
      end
      @consumer.consume
    end

    def consume_two
      @cancel_queue.subscribe do |_, payload|
        @cancel_signal.add_messages(parse_data(payload))
        Naily.logger.debug "Process message from cancel queue: #{payload.inspect}"
      end
    end

    def dispatch(payload)
      parse_data(payload).each_with_index do |message, i|
        begin
          dispatch_message message
        rescue StopIteration
          Naily.logger.debug "Dispatching aborted by #{message['method']}"
          abort_messages messages[(i + 1)..-1]
          break
        rescue => ex
          Naily.logger.error "Error running RPC method #{message['method']}: #{ex.message}, trace: #{ex.backtrace.inspect}"
          return_results message, {
            'status' => 'error',
            'error'  => "Error occurred while running method '#{message['method']}'. Inspect Orchestrator logs for the details."
          }
        end
      end
    end

    def dispatch_message(data)
      Naily.logger.debug "Dispatching message: #{data.inspect}"

      if Naily.config.fake_dispatch
        Naily.logger.debug "Fake dispatch"
        return
      end

      unless @delegate.respond_to?(data['method'])
        Naily.logger.error "Unsupported RPC call '#{data['method']}'"
        return_results data, {
          'status' => 'error',
          'error'  => "Unsupported method '#{data['method']}' called."
        }
        return
      end

      Naily.logger.info "Processing RPC call '#{data['method']}'"
      if data['method'].to_s == 'deploy'
        @delegate.send(data['method'], data, @cancel_signal)
      else
        @delegate.send(data['method'], data)
      end
    end

    def return_results(message, results)
      if results.is_a?(Hash) && message['respond_to']
        reporter = Naily::Reporter.new(@producer, message['respond_to'], message['args']['task_uuid'])
        reporter.report results
      end
    end

    def parse_data(data)
      Naily.logger.debug "Got message with payload #{data.inspect}"
      messages = nil
      begin
        messages = JSON.load(data)
      rescue => e
        Naily.logger.error "Error deserializing payload: #{e.message}, trace: #{e.backtrace.inspect}"
      end
      messages.is_a?(Array) ? messages : [messages]
    end

    def abort_messages(messages)
      return unless messages && messages.size > 0
      messages.each do |message|
        begin
          Naily.logger.debug "Aborting '#{message['method']}'"
          err_msg = {
            'status' => 'error',
            'error' => 'Task aborted',
            'progress' => 100
          }

          if message['args']['nodes'].instance_of?(Array)
            err_nodes = message['args']['nodes'].map do |node|
              {'uid' => node['uid'], 'status' => 'error', 'error_type' => 'provision', 'progress' => 0}
            end

            err_msg.merge!('nodes' => err_nodes)
          end

          return_results(message, err_msg)
        rescue => ex
          Naily.logger.debug "Failed to abort '#{message['method']}': #{ex.inspect}"
        end
      end
    end
  end
end
