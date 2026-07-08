import { app as electronApp } from 'electron';
import { Orchestrator, type OrchestratorInitProps } from './orchestrator';
import { createOrchestratorDeps } from './orchestrator.deps';

let ORCHESTRATOR: Orchestrator | null = null;

// `electronApp` instance is crated outsid of this code.
// Here we listen to the `electronApp.on('ready')` event and 
// create the `Orchestrator` instance, and initialize the "glue"
// between the `electronApp` and the `Orchestrator`.
electronApp.on('ready', async () => {
  // create instance
  const props: OrchestratorInitProps = {
    DEPS: await createOrchestratorDeps(),
    electronApp,
  };
  ORCHESTRATOR = new Orchestrator(props);

  // initialize
  await ORCHESTRATOR.initializeElectronApp();
});
