import assert from "node:assert/strict";

export async function runIntrospectionProbes({
  Annotation,
  END,
  START,
  StateGraph,
}) {
  const State = Annotation.Root({ value: Annotation });
  const step = (state) => state;

  const linear = new StateGraph(State)
    .addNode("step", step)
    .addEdge(START, "step")
    .addEdge("step", END)
    .compile({ interruptBefore: ["step"] });
  assert.deepEqual(Object.keys(linear.builder.nodes), ["step"]);
  assert.deepEqual(
    [...linear.builder.edges],
    [
      [START, "step"],
      ["step", END],
    ],
  );
  assert.deepEqual(linear.interruptBefore, ["step"]);
  assert.deepEqual(
    Object.keys((await linear.getGraphAsync({ xray: 0 })).nodes),
    [START, "step", END],
  );

  const branching = new StateGraph(State)
    .addNode("route", step)
    .addNode("target", step)
    .addEdge(START, "route")
    .addConditionalEdges("route", () => "target", { target: "target" })
    .addEdge("target", END)
    .compile();
  assert.deepEqual(
    Object.values(branching.builder.branches.route).map(
      (branch) => branch.ends,
    ),
    [{ target: "target" }],
  );

  const unknownBranch = new StateGraph(State)
    .addNode("route", step)
    .addNode("target", step)
    .addEdge(START, "route")
    .addConditionalEdges("route", () => "target")
    .addEdge("target", END)
    .compile();
  assert.deepEqual(
    Object.values(unknownBranch.builder.branches.route).map(
      (branch) => branch.ends,
    ),
    [undefined],
  );

  const declaredNodeDestinations = new StateGraph(State)
    .addNode("route", step, { ends: ["target"] })
    .addNode("target", step)
    .addEdge(START, "route")
    .addEdge("target", END)
    .compile();
  assert.deepEqual(declaredNodeDestinations.builder.nodes.route.ends, [
    "target",
  ]);

  const joined = new StateGraph(State)
    .addNode("left", step)
    .addNode("right", step)
    .addNode("joined", step)
    .addEdge(START, "left")
    .addEdge(START, "right")
    .addEdge(["left", "right"], "joined")
    .addEdge("joined", END)
    .compile();
  assert.deepEqual(
    [...joined.builder.waitingEdges],
    [[["left", "right"], "joined"]],
  );
  assert.ok(
    ![...joined.builder.edges].some(([, target]) => target === "joined"),
  );

  const child = new StateGraph(State)
    .addNode("inner", step)
    .addEdge(START, "inner")
    .addEdge("inner", END)
    .compile();
  const parent = new StateGraph(State)
    .addNode("child", child)
    .addEdge(START, "child")
    .addEdge("child", END)
    .compile();
  assert.equal(parent.builder.nodes.child.subgraphs?.[0], child);
}
