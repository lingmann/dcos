#!/usr/bin/env ruby
require 'open3'
require 'find'
require 'fileutils'

class CopyLibs

  attr_reader :analysed, :libraries

  def initialize(sources, output_directory)
    @sources, @output_directory = sources, output_directory
    @libraries = {}
    @analysed = false
  end # def

  def analyse
    @sources.each do |source|
      raise "not readable: #{source}" unless File.readable?(source)

      if File.directory?(source)
        Find.find(source) do |file|
          dependencies(file) if File.executable?(file) && File.file?(file)
        end
      else
        dependencies(source)
      end
    end
    @analysed = true
  end # def

  def dependencies(infile, depth = 0)
    raise "recursion too deep" if depth > 100

    puts "checking #{infile}"
    cmd = "ldd '#{infile}'"
    Open3.popen3(cmd) do |stdin, stdout, stderr, wait_thr|
      exit_status = wait_thr.value
      return unless exit_status.success?

      while line = stdout.gets
        line = line.gsub(/^\s/, '').gsub(/\s+/, ' ')
        if /^(?<library>.*?)\s+=>\s+(?<library_path>\/.*?)\s+\([0-9a-fx]+\)/ =~ line

          if !@libraries.key?(library) && File.exist?(library_path)
            @libraries[library] = library_path
            dependencies(library_path, depth + 1)
          end
        end
      end # while

    end # Open3.popen3
  end # def

  def copy
    raise "not a writable directory: #{@output_directory}" unless \
      File.directory?(@output_directory) && File.writable?(@output_directory)

    analyse() unless @analysed

    @libraries.each do |library, library_path|
      puts "copy #{library_path} => #{@output_directory}"
      FileUtils.cp(library_path, @output_directory, :preserve => true)
    end
  end
end

output_directory = ARGV.pop
sources = ARGV

cl = CopyLibs.new(sources, output_directory)
begin
  cl.copy
rescue => e
  abort e.message
end
