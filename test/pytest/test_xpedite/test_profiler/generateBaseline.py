"""
Python module to clean up and generate files used with Xpedite pytests.
This module generates baseline profile information and probe state information.
Baseline information for profiles is created by generating a Jupyter notebook
for a new Xpedite run, and copying over the .xpd profile information file and
.data files from the xpedite run to a tar file organized by application and scenario.
The application is also used to test automatically generating profile information
as well as testing probe states.

Author:  Brooke Elizabeth Cantwell, Morgan Stanley
"""

import os
import json
import cPickle as pickle
import argparse
from shutil                               import copy
from xpedite.benchmark                    import makeBenchmark
from test_xpedite.test_profiler.profile   import buildNotebook, loadProbes, generateProfileInfoFile
from test_xpedite                         import (
                                            REPORT_CMD_BASELINE_PATH,
                                            BASELINE_CPU_INFO_PATH, PROBE_CMD_BASELINE_PATH,
                                            XPEDITE_APP_INFO_PARAMETER_PATH, TXN_COUNT,
                                            THREAD_COUNT, PARAMETERS_DATA_DIR, EXPECTED_RESULTS,
                                            GENERATE_CMD_BASELINE_PATH
                                          )
from test_xpedite.test_profiler.app       import TargetLauncher
from test_xpedite.test_profiler.profile   import generateProfiles
from test_xpedite.test_profiler.context   import Context
from test_xpedite.test_profiler.scenario  import ScenarioLoader, ScenarioType

BENCHMARK = 'benchmark'
BENCHMARK_APP_INFO_PATH = os.path.join(BENCHMARK, 'appinfo.txt')
APPS = ['allocatorApp', 'dataTxnApp', 'multiThreadedApp', 'slowFixDecoderApp']

def benchmarkProfile(context, scenario):
  """
  Create a benchmark for an application
  """
  with TargetLauncher(context, scenario) as app:
    report = generateProfiles(app.xpediteApp, scenario, context)
    makeBenchmark(report.profiles, scenario.dataDir)
    benchmarkAppInfoPath = os.path.join(scenario.dataDir, BENCHMARK_APP_INFO_PATH)
    replaceWorkspace(benchmarkAppInfoPath, context.workspace, benchmarkAppInfoPath)

def replaceWorkspace(filePath, workspace, destination):
  """
  Trim the workspace path from file paths and rewrite to destination
  """
  with open(filePath, 'r') as fileHandle:
    appInfoStr = fileHandle.read()
  appInfoStr = appInfoStr.replace(workspace, '')
  with open(destination, 'w') as fileHandle:
    fileHandle.write(appInfoStr)

def generateBaseline(context, scenario):
  """
  Generate the following files for an application scenario:
  Parameters:
    - Xpedite application information file - (xpedite-appinfo.txt)
      Used to test building of notebooks
  Expected Results:
    - Profile data file generated from building a Jupyter notebook - (reportCmdBaseline.xpd)
      Used to compare results from profiling against previous results
    - Xpedite .data files - (xpedite-<app_name>-<run_id>.data)
      Used to recreate profiles from the same sample files to test profiling
    - An automatically generated profile information file (generateCmdBaseline.py)
      Used to test Xpedite's profile info generate functionality
    - Serialized probe baseline map - (probeCmdBaseline.pkl)
      Used to compare probe states generated by an xpedite app to baseline probes
  These files are stored in tar files separated by application and scenario
  """
  os.mkdir(os.path.join(scenario.dataDir, PARAMETERS_DATA_DIR))
  os.mkdir(os.path.join(scenario.dataDir, EXPECTED_RESULTS))
  with scenario as _:
    if scenario.scenarioType == ScenarioType.Benchmark:
      benchmarkProfile(context, scenario)
    _, dataFilePath, report, fullCpuInfo, dataFiles = buildNotebook(context, scenario)
    copy(dataFilePath, os.path.join(scenario.dataDir, REPORT_CMD_BASELINE_PATH))

    for dataFile in dataFiles:
      copy(dataFile, os.path.join(scenario.dataDir, PARAMETERS_DATA_DIR, os.path.basename(dataFile)))
    replaceWorkspace(
      report.app.appInfoPath, context.workspace, os.path.join(scenario.dataDir, XPEDITE_APP_INFO_PARAMETER_PATH)
    )

    with open(os.path.join(scenario.dataDir, BASELINE_CPU_INFO_PATH), 'w') as fileHandle:
      json.dump(fullCpuInfo, fileHandle)

    probes = loadProbes(context, scenario)

    copy(os.path.abspath(
      generateProfileInfoFile(report.app, probes)), os.path.join(scenario.dataDir, GENERATE_CMD_BASELINE_PATH
    ))

    baselineProbeMap = {}
    for probe in probes:
      baselineProbeMap[probe.sysName] = probe
    with open(os.path.join(scenario.dataDir, PROBE_CMD_BASELINE_PATH), 'wb') as probeFileHandle:
      probeFileHandle.write(pickle.dumps(baselineProbeMap)) # pylint: disable=c-extension-no-member

def main():
  """
  Parse arguments fron the generate baseline shell script, initalize test context, and generate
  baseline files for each application scenario.
  """
  defaultWorkspace = os.path.join(os.path.abspath(__file__).split('/test/')[0], '')
  parser = argparse.ArgumentParser()
  parser.add_argument('--rundir', help='temporary directory where files have been unzipped')
  parser.add_argument('--txncount', default=TXN_COUNT, help='number of transactions to generate')
  parser.add_argument('--threadcount', default=THREAD_COUNT, help='number of threads to use in application')
  parser.add_argument('--workspace', default=defaultWorkspace, help='prefix to trim off of file paths')
  args = parser.parse_args()

  context = Context(args.txncount, args.threadcount, args.workspace)
  for scenario in ScenarioLoader().loadScenarios(args.rundir, APPS):
    generateBaseline(context, scenario)

if __name__ == '__main__':
  main()
