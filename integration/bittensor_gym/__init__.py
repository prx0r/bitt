"""bittensor_gym — Bridge between Bittensor subnet economies and MWGym evolution.

This package plugs Bittensor's live evaluation networks into MWGym's
CGE (Competitive Game Environment) framework, enabling:

  - Training workers against Bittensor subnet objectives
  - Evolving worker policies via CGE adversarial curriculum
  - Transferring lab-trained organisms into live TAO emission networks
  - Tracking cost/quality/runtime across synthetic and economic worlds

Target subnets:
  SN67  Harnyx    — deep research (score + cost + latency + novelty)
  SN62  Ridges    — coding/SWE agents (executable tests)
  SN6   Numinous  — forecasting + persistent memory
  SN15  ORO       — shopping/product agents (ShoppingBench ground truth)
"""

__version__ = "0.1.0"
