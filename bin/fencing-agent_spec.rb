require 'rubygems'
require 'rspec'
require 'mocha/api'
# stub the root rights for agent script under test
Process.stubs(:euid).returns(0)
# use load for agent script w/o '.rb' extension
require './bin/fencing-agent'

# fixtures
  $xml_all_ok = <<END
<xpath-query>
  <nvpair id="status-node-7.test.domain.local-root_free" name="root_free" value="5"/>
  <nvpair id="status-node-8.test.domain.local-root_free" name="root_free" value="5"/>
  <nvpair id="status-node-9.test.domain.local-root_free" name="root_free" value="5"/>
</xpath-query>
END
  $xml_need_fence1 = <<END
<xpath-query>
  <nvpair id="status-node-7.test.domain.local-root_free" name="root_free" value="5"/>
  <nvpair id="status-node-8.test.domain.local-root_free" name="root_free" value="5"/>
  <nvpair id="status-node-9.test.domain.local-root_free" name="root_free" value="0"/>
</xpath-query>
END
  $xml_need_fence2 = <<END
<xpath-query>
  <nvpair id="status-node-7.test.domain.local-root_free" name="root_free" value="0"/>
  <nvpair id="status-node-8.test.domain.local-root_free" name="root_free" value="5"/>
  <nvpair id="status-node-9.test.domain.local-root_free" name="root_free" value="0"/>
</xpath-query>
END
  $fl = StringIO.new("target")

describe FenceAgent do
  before :each do
    logger = Logger.new(STDOUT)
    logger.level = Logger::DEBUG
    @agent = FenceAgent.new(logger)
    @agent.stubs(:random).returns(0)
    File.stub(:exist?).with("/etc/nailgun_systemtype").and_return(true)
    File.stub(:open).with("/etc/nailgun_systemtype", "r").and_return($fl)
  end

  describe "#new" do
    it "takes logger and url parameters and returns a nailgun agent instance" do
      @agent.should be_an_instance_of FenceAgent
    end
  end

  # Fence daemon tests
  describe "#check_and_fence" do
    before :each do
      @agent.stubs(:is_corosync_up).returns(true)
      @agent.stubs(:get_system_type).returns("target")
    end

    it "Check N/A: should return 1, if system type file is missing" do
      File.stub(:exist?).with("/etc/nailgun_systemtype").and_return(false)
      @agent.check_and_fence.should eq(1)
    end

    it "Check N/A: should return 1, if fence action is not applicable because of wrong system type" do
      @agent.stubs(:get_system_type).returns("bootstrap")
      @agent.check_and_fence.should eq(1)
    end

    it "Check N/A: should return 1, if corosync is not ready" do
      @agent.stub(:is_corosync_up).and_return(false)
      @agent.check_and_fence.should eq(1)
    end

    it "Check N/A: should return 1, if none of free space monitoring ocf resources ready" do
      @agent.stubs(:get_free_root_space_from_CIB).returns(nil)
      @agent.check_and_fence.should eq(1)
    end

    it "Check PASSED: should return 0, if nodes in the cluster don't need fencing by root free space criteria" do
      @agent.stubs(:get_free_root_space_from_CIB).returns(REXML::Document.new($xml_all_ok).root.elements['/xpath-query'])
      @agent.check_and_fence.should eq(0)
    end

    it "Check FAILED: if one node must be fenced and is online, should issue fence command to corosync and return 2" do
      @agent.stubs(:get_free_root_space_from_CIB).returns(REXML::Document.new($xml_need_fence1).root.elements['/xpath-query'])
      expected_node = "node-9.test.domain.local"
      expected_nodes = [ expected_node ]
      @agent.stub(:exec).with(
        "/usr/sbin/cibadmin --query --xpath \"//node_state[@uname='#{expected_node}']\" | grep -q 'crmd=\"online\"'"
      ).and_return(0)
      @agent.stub(:exec).with(
        "/usr/sbin/crm --force node fence #{expected_node}"
      ).and_return(0)
      @agent.should_receive(:is_offline).with(expected_node).exactly(1).times.and_return(false)
      @agent.should_receive(:fence_nodes).with(expected_nodes).exactly(1).times.and_return(2)
      @agent.check_and_fence.should eq(2)
    end

    it "Check FAILED: if some nodes must be fenced and are online, should issue fence commands to corosync and return 2" do
      @agent.stubs(:get_free_root_space_from_CIB).returns(REXML::Document.new($xml_need_fence2).root.elements['/xpath-query'])
      expected_node1 = "node-7.test.domain.local"
      expected_node2 = "node-9.test.domain.local"
      expected_nodes = [ expected_node1, expected_node2 ]
      expected_nodes.each do |node|
        @agent.stub(:exec).with(
          "/usr/sbin/cibadmin --query --xpath \"//node_state[@uname='#{node}']\" | grep -q 'crmd=\"online\"'"
        ).and_return(0)
        @agent.stub(:exec).with(
          "/usr/sbin/crm --force node fence #{node}"
        ).and_return(0)
        @agent.should_receive(:is_offline).with(node).exactly(1).times.and_return(false)
      end
      @agent.should_receive(:fence_nodes).with(expected_nodes).exactly(1).times.and_return(2)
      @agent.check_and_fence.should eq(2)
    end

    it "Check FAILED: should return 3, if some nodes are online and has been ordered to fence, but some of crm commands were not issued for some reasons" do
      @agent.stubs(:get_free_root_space_from_CIB).returns(REXML::Document.new($xml_need_fence2).root.elements['/xpath-query'])
      expected_node1 = "node-7.test.domain.local"
      expected_node2 = "node-9.test.domain.local"
      expected_nodes = [ expected_node1, expected_node2 ]
      expected_nodes.each do |node|
        @agent.stub(:exec).with(
          "/usr/sbin/cibadmin --query --xpath \"//node_state[@uname='#{node}']\" | grep -q 'crmd=\"online\"'"
        ).and_return(0)
        @agent.should_receive(:is_offline).with(node).exactly(1).times.and_return(false)
      end
      @agent.stub(:exec).with(
        "/usr/sbin/crm --force node fence #{expected_node1}"
      ).and_return(0)
      @agent.stub(:exec).with(
        "/usr/sbin/crm --force node fence #{expected_node2}"
      ).and_return(6)
      @agent.should_receive(:fence_nodes).with(expected_nodes).exactly(1).times.and_return(3)
      @agent.check_and_fence.should eq(3)
    end

    it "Check consider PASSED behavior: should exclude itself from the fencing and return 0" do
      @agent.stubs(:get_free_root_space_from_CIB).returns(REXML::Document.new($xml_need_fence1).root.elements['/xpath-query'])
      @agent.stubs(:is_offline).returns(false)
      @agent.stubs(:system_info).returns({ :fqdn => 'node-9.test.domain.local', :name => 'node-9' })
      @agent.check_and_fence.should eq(0)
    end

    it "Check consider PASSED behavior: should exclude offline nodes from the fencing and return 0" do
      @agent.stubs(:get_free_root_space_from_CIB).returns(REXML::Document.new($xml_need_fence1).root.elements['/xpath-query'])
      @agent.stubs(:is_offline).returns(true)
      @agent.check_and_fence.should eq(0)
    end
  end
end
