const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { sample } = require('../assets/demo.js');
const registry = JSON.parse(fs.readFileSync('api/runs.json'));
for (const run of registry.runs) {
  test(`${run.run_id}: bounded, coherent samples preserve fixtures and configuration`, () => {
    const baseline = Object.fromEntries(Object.entries({summary:'summary',resources:'resources',storage:'storage',interconnect:'interconnect',dataMovement:'data-movement'}).map(([key,file]) => [key,JSON.parse(fs.readFileSync(`api/runs/${run.run_id}/${file}.json`))]));
    const original = JSON.stringify(baseline);
    for (let tick=1;tick<=240;tick++) {
      const result = sample(baseline,tick), m = result.summary.metrics;
      assert.deepEqual(result.summary.configuration,baseline.summary.configuration);
      assert.notEqual(m.training_tokens_per_second,baseline.summary.metrics.training_tokens_per_second);
      assert.equal(m.checkpoint_frequency_steps,baseline.summary.metrics.checkpoint_frequency_steps);
      for (const [key,value] of Object.entries(m)) {
        assert.ok(Number.isFinite(value) && value>=0,key);
        if (key.endsWith('_ratio')) assert.ok(value<=1,key);
        if (key.endsWith('_percent')) assert.ok(value<=100,key);
        if (key.endsWith('_total')) assert.equal(value,baseline.summary.metrics[key]);
      }
      const nodes=result.resources.nodes,gpus=nodes.flatMap(n=>n.gpus);
      assert.ok(Math.abs(m.gpu_utilization_percent-gpus.reduce((s,g)=>s+g.utilization_percent,0)/gpus.length)<.051);
      assert.ok(Math.abs(m.host_memory_used_gib-nodes.reduce((s,n)=>s+n.memory_used_gib,0))<.051);
      for (const n of nodes) assert.ok(n.memory_used_gib<=n.memory_total_gib);
      for (const path of result.dataMovement.paths) {
        assert.ok(Math.abs(path.data_movement_effective_bandwidth_bytes_per_second-path.data_movement_bytes_total/path.data_movement_duration_seconds)<1);
        assert.equal(path.baseline_utilization_ratio,path.data_movement_effective_bandwidth_bytes_per_second/path.baseline_bandwidth_bytes_per_second);
      }
    }
    assert.equal(JSON.stringify(baseline),original);
  });
}
