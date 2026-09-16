// Configuration reaches the application through environment variables, which are process-global
// (see SynthiaApiFactory for why that is the only mechanism that works under minimal hosting).
// Two test classes booting differently-configured applications at the same time would therefore
// read each other's settings. Serialising the assembly is the honest fix; the alternative is a
// suite that passes except when it does not.
[assembly: CollectionBehavior(DisableTestParallelization = true)]
