#!/usr/bin/env ruby

#    Copyright 2014 Mirantis, Inc.
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

begin
  require 'rubygems'
rescue LoadError
end
require 'ohai/system'
require 'logger'
require 'open3'
require 'rexml/document'

unless Process.euid == 0
  puts "You must be root"
  exit 1
end

ENV['PATH'] = "/bin:/usr/bin:/sbin:/usr/sbin:/usr/local/bin:/usr/local/sbin"

class FenceAgent
  def initialize(logger)
    @logger = logger
    @os = Ohai::System.new()
    @os.all_plugins
  end

  def system_info
    {
      :fqdn => (@os[:fqdn].strip rescue @os[:hostname].strip rescue nil),
      :hostname => (@os[:hostname].strip rescue nil),
    }.delete_if { |key, value| value.nil? or value.empty? or value == "Not Specified" }
  end

  # Check free root space for all nodes in the corosync cluster, if any up and running
  # Do not wait or check for the fence actions results, if any were taken (it is in cluster's responsibility)
  # TODO report to nailgun if fencing actions were taken
  # * return 0, if nodes in the cluster don't need fencing by root free space criteria
  # * return 1, if fence action is not applicable atm, e.g. corosync is absent or not accessible yet, or node wasn't yet provisioned
  # * return 2, if some nodes has been ordered to fence and all corresponding crm commands were issued to corosync
  # * return 3, if some nodes has been ordered to fence, but some of crm commands were not issued for some reasons
  def check_and_fence
    # Privates

    # for unit tests' stubs
    def random(s,n)
      s+rand(n)
    end

    # sleep and exec cmd
    def exec(cmd,sleep_time)
      unless sleep_time.nil? or sleep_time == 0
        @logger.info("Sleep #{Process.pid} for #{sleep_time}s, before issuing cmd:#{cmd}")
        sleep(sleep_time)
      end
      Process.fork  do
        Process.exec(cmd)
      end
      Process.wait
      $?.exitstatus
    end

    # * return target, if provisioned
    # * return bootstrap, if not provisioned yet
    def get_system_type(filename)
      fl = File.open(filename, "r")
      state = fl.readline.rstrip
      fl.close
      state
    end

    # * return true, if corosync running and CIB is up
    def is_corosync_up
      cmd = "/usr/sbin/crm_attribute --type crm_config --query --name dc-version &>/dev/null"
      exec(cmd,random(5,10)) == 0
    end

    # assume is_corosync_up true
    # * return xml with free root space data from CIB, or nil
    def get_free_root_space_from_CIB
      cmd = "/usr/sbin/cibadmin --query --xpath \"//nvpair[@name='root_free']\""
      sleep(random(3,5))
      REXML::Document.new(Open3.popen3(cmd)[1].read).root.elements['/xpath-query'] rescue nil
    end

    # assume is_corosync_up true
    # * return true, if node is OFFLINE (or not applicable for any actions by corosync cluster services)
    def is_offline(fqdn)
      cmd = "/usr/sbin/cibadmin --query --xpath \"//node_state[@uname='#{fqdn}']\" | grep -q 'crmd=\"online\"'"
      exec(cmd,random(5,10)) > 0
    end

    # assume is_corosync_up true
    # issue fencing action to cluster services for given nodes
    # * return 2, if some nodes has been ordered to fence and all crm command has been issued.
    # * return 3, if some nodes has been ordered to fence, but some of crm commands was not issued for some reasons.
    def fence_nodes(nodes_to_fence)
      failed = false
      nodes_to_fence.each do |node|
        cmd = "/usr/sbin/crm --force node fence #{node}"
        if exec(cmd,random(15,15)) > 0
          @logger.error("Cannot issue the command: #{cmd}")
          failed = true
        else
          @logger.error("Issued the fence action: #{cmd}")
        end
      end
      return 2 unless failed
      3
    end

    # Start check for cluster's free root space
    @logger.debug("Starting cluster free root space check")
    if File.exist?("/etc/nailgun_systemtype")
      # exit, if node is not provisioned yet
      if get_system_type("/etc/nailgun_systemtype") != "target"
        @logger.debug("The system state is not 'target' yet, exiting with 1")
        return 1
      end
    else
      @logger.debug("The /etc/nailgun_systemtype file is missing, exiting with 1")
      return 1
    end
    # exit, if cibadmin tool doesn't exist yet
    unless is_corosync_up
      @logger.debug("Corosync is absent or not ready yet, exiting with 1")
      return 1
    end
    # query CIB for nodes' root free space
    stanzas = get_free_root_space_from_CIB
    if stanzas.nil?
      @logger.debug("Free space monitoring resource is not configured yet, exiting with 1")
      return 1
    end
    nodes_to_fence = []
    # for every node in the cluster
    stanzas.each_element do |e|
      items = e.attributes
      # get the node's fqdn and free space at root partition from CIB
      line = { :fqdn => /^status-(.*)-root_free$/.match(items['id'])[1], :root_free => items['value'] }
      # get the node's status from CIB
      @logger.debug("Got fqdn:#{line[:fqdn]}, root free space:#{line[:root_free]}G")
      # if node is not the agent's one, and node's root free space is zero, and its status is online, add it to the list of nodes must be fenced
      cmd = "/usr/sbin/cibadmin --query --xpath \"//node_state[@uname='#{line[:fqdn]}']\" | grep -q 'crmd=\"online\"'"
      if line[:root_free].to_i == 0
        offline = is_offline(line[:fqdn])
        @logger.debug("Ignoring offline node #{line[:fqdn]}") if offline
      end
      itself = (system_info[:fqdn] == line[:fqdn] or system_info[:name] == line[:fqdn])
      @logger.debug("Ignoring my own node #{line[:fqdn]} (cannot shoot myself)") if itself and line[:root_free].to_i == 0
      nodes_to_fence.push(line[:fqdn]) unless line[:root_free].to_i > 0 or offline or itself or nodes_to_fence.include?(line[:fqdn])
    end
    # fence the failed nodes, if any, by random delay (15..30) and report an alert
    unless nodes_to_fence.empty?
      result = fence_nodes(nodes_to_fence)
      @logger.error("Cluster has FAILED free root space check!")
      return result
    else
      @logger.debug("Cluster has PASSED free root space check successfully")
      return 0
    end
  end
end

# skip it, if under unit testing
if $0 == __FILE__
  logger = Logger.new(STDOUT)
  logger.level = Logger::DEBUG

  agent = FenceAgent.new(logger)
  begin
    agent.check_and_fence
  rescue => ex
    logger.error "Cluster free root space check cannot be performed: #{ex.message}\n#{ex.backtrace}"
  end
end
