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

require 'naily/reporter'

module Naily
  class Dispatcher
    def initialize(producer)
      @orchestrator = Astute::Orchestrator.new(nil, log_parsing=true)
      @producer = producer
      @provisionLogParser = Astute::LogParser::ParseProvisionLogs.new
    end

    def echo(args)
      Naily.logger.info 'Running echo command'
      args
    end

    #
    #  Main worker actions
    #

    def download_release(data)
      # Example of message = {
      # {'method': 'download_release',
      # 'respond_to': 'download_release_resp',
      # 'args':{
      #     'task_uuid': 'task UUID',
      #     'release_info':{
      #         'release_id': 'release ID',
      #         'redhat':{
      #             'license_type' :"rhn" or "rhsm",
      #             'username': 'username',
      #             'password': 'password',
      #             'satellite': 'satellite host (for RHN license)'
      #             'activation_key': 'activation key (for RHN license)'
      #         }
      #     }
      # }}
      Naily.logger.info("'download_release' method called with data: #{data.inspect}")
      reporter = Naily::Reporter.new(@producer, data['respond_to'], data['args']['task_uuid'])
      release_info = data['args']['release_info']['redhat']
      begin
        result = @orchestrator.download_release(reporter, data['args']['task_uuid'], release_info)
      rescue Timeout::Error
        msg = "Timeout of release download is exceeded."
        Naily.logger.error msg
        reporter.report({'status' => 'error', 'error' => msg})
        return
      end
    end

    def check_redhat_credentials(data)
      release = data['args']['release_info']
      task_id = data['args']['task_uuid']
      reporter = Naily::Reporter.new(@producer, data['respond_to'], task_id)
      @orchestrator.check_redhat_credentials(reporter, task_id, release)
    end

    def check_redhat_licenses(data)
      release = data['args']['release_info']
      nodes = data['args']['nodes']
      task_id = data['args']['task_uuid']
      reporter = Naily::Reporter.new(@producer, data['respond_to'], task_id)
      @orchestrator.check_redhat_licenses(reporter, task_id, release, nodes)
    end

    def provision(data)
      Naily.logger.info("'provision' method called with data: #{data.inspect}")

      reporter = Naily::Reporter.new(@producer, data['respond_to'], data['args']['task_uuid'])
      begin
        @orchestrator.provision(reporter,
                                data['args']['provisioning_info']['engine'],
                                data['args']['provisioning_info']['nodes'])
      rescue => e
        Naily.logger.error "Error running provisioning: #{e.message}, trace: #{e.backtrace.inspect}"
        raise StopIteration
      end

      @orchestrator.watch_provision_progress(
        reporter, data['args']['task_uuid'], data['args']['provisioning_info']['nodes'])
    end

    def deploy(data)
      Naily.logger.info("'deploy' method called with data: #{data.inspect}")

      reporter = Naily::Reporter.new(@producer, data['respond_to'], data['args']['task_uuid'])
      begin
        @orchestrator.deploy(reporter, data['args']['task_uuid'], data['args']['deployment_info'])
        reporter.report('status' => 'ready', 'progress' => 100)
      rescue Timeout::Error
        msg = "Timeout of deployment is exceeded."
        Naily.logger.error msg
        reporter.report('status' => 'error', 'error' => msg)
      end
    end

    def verify_networks(data)
      reporter = Naily::SubtaskReporter.new(@producer, data['respond_to'], data['args']['task_uuid'], data['subtasks'])
      result = @orchestrator.verify_networks(reporter, data['args']['task_uuid'], data['args']['nodes'])
      report_result(result, reporter)
    end

    def dump_environment(data)
      task_id = data['args']['task_uuid']
      reporter = Naily::Reporter.new(@producer, data['respond_to'], task_id)
      @orchestrator.dump_environment(reporter, task_id, data['args']['lastdump'])
    end

    def remove_nodes(data)
      task_uuid = data['args']['task_uuid']
      reporter = Naily::Reporter.new(@producer, data['respond_to'], task_uuid)
      nodes = data['args']['nodes']
      engine = data['args']['engine']

      result = if nodes.empty?
        Naily.logger.debug("#{task_uuid} Node list is empty")
        nil
      else
        @orchestrator.remove_nodes(reporter, task_uuid, engine, nodes)
      end

      report_result(result, reporter)
    end

    def reset_environment(data)
      remove_nodes(data)
    end

    #
    #  Service worker actions
    #

    def stop_deploy_task(data, service_data)
      Naily.logger.debug("'stop_deploy_task' service method called with data: #{data.inspect}")
      target_task_uuid = data['args']['stop_task_uuid']
      task_uuid = data['args']['task_uuid']

      return unless task_in_queue?(target_task_uuid, service_data[:tasks_queue])

      Naily.logger.debug("Cancel task #{target_task_uuid}. Start")
      if target_task_uuid == service_data[:tasks_queue].current_task_id
        reporter = Naily::Reporter.new(@producer, data['respond_to'], task_uuid)
        result = stop_current_task(data, service_data, reporter)
        report_result(result, reporter)
      else
        replace_future_task(data, service_data)
      end
    end

    private

    def task_in_queue?(task_uuid, tasks_queue)
      tasks_queue.task_in_queue?(task_uuid)
    end

    def replace_future_task(data, service_data)
      target_task_uuid = data['args']['stop_task_uuid']
      task_uuid = data['args']['task_uuid']

      new_task_data = data_for_rm_nodes(data)
      Naily.logger.info("Replace running task #{target_task_uuid} to new #{task_uuid} with data: #{new_task_data.inspect}")
      service_data[:tasks_queue].replace_task(target_task_uuid, new_task_data)
    end

    def stop_current_task(data, service_data, reporter)
      target_task_uuid = data['args']['stop_task_uuid']
      task_uuid = data['args']['task_uuid']
      nodes = data['args']['nodes']

      Naily.logger.info "Try to kill running task #{target_task_uuid}"
      service_data[:main_work_thread].raise("StopDeploy")
      sleep 0.1 while service_data[:main_work_thread].status != 'sleep'

      if service_data[:tasks_queue].current_task_method == 'deploy'
        @orchestrator.stop_puppet_deploy(reporter, task_uuid, nodes)
        result = @orchestrator.remove_nodes(reporter, task_uuid, data['args']['engine'], nodes)
      else
        result = @orchestrator.stop_provision(reporter, task_uuid, nodes)
      end

      service_data[:main_work_thread].run
      return result
    end

    def data_for_rm_nodes(data)
      data['method'] = 'remove_nodes'
      data
    end

    def report_result(result, reporter)
      result = {} unless result.instance_of?(Hash)
      status = {'status' => 'ready', 'progress' => 100}.merge(result)
      reporter.report(status)
    end
  end
end
