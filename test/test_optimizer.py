"""Test `sirfshampoo.optimizer` module."""

from collections import OrderedDict

from torch import manual_seed, rand
from torch.nn import Linear, MSELoss, ReLU, Sequential, Sigmoid

from sirfshampoo.optimizer import SIRFShampoo


def test__one_param_group_per_preconditioner():
    """Test creation of parameter groups (one per pre-conditioner)."""
    manual_seed(0)
    D_in, D_hidden, D_out = 5, 4, 3

    # use a nested network
    inner = Sequential(
        OrderedDict(
            {
                "linear": Linear(D_hidden, D_hidden, bias=False),
                "sigmoid": Sigmoid(),
            }
        )
    )
    model = Sequential(
        OrderedDict(
            {
                "linear1": Linear(D_in, D_hidden),
                "relu1": ReLU(),
                "inner": inner,
                "linear2": Linear(D_hidden, D_out),
            }
        )
    )
    defaults = {"beta1": 0.001, "alpha1": 0.9, "kappa": 0.0}

    # one parameter group
    optimizer = SIRFShampoo(model, verbose_init=True)
    assert len(optimizer.param_groups) == 3
    assert optimizer.param_groups == [
        {"params": [model.linear1.weight, model.linear1.bias], **defaults},
        {"params": [model.inner.linear.weight], **defaults},
        {"params": [model.linear2.weight, model.linear2.bias], **defaults},
    ]

    # two parameter groups (sub-set of parameters), one with modified defaults
    param_groups = [
        {
            "params": [model.linear1.weight, model.linear1.bias, model.linear2.bias],
            **defaults,
            "lam": 1234.0,  # change lam to verify it is passed through the overwrite
        },
        {"params": [model.inner.linear.weight]},
    ]
    optimizer = SIRFShampoo(model, params=param_groups, verbose_init=True)
    assert len(optimizer.param_groups) == 3
    assert optimizer.param_groups == [
        {
            "params": [model.linear1.weight, model.linear1.bias],
            **defaults,
            "lam": 1234.0,
        },
        {"params": [model.inner.linear.weight], **defaults},
        {"params": [model.linear2.bias], **defaults, "lam": 1234.0},
    ]

    # two parameter groups (sub-set of parameters), one with modified defaults,
    # and parameters in one layer split into different groups such that they cannot
    # be treated jointly
    param_groups = [
        {
            "params": [model.linear1.weight, model.linear2.bias],
            **defaults,
            "lam": 1234.0,  # change lam to verify it is passed through the overwrite
        },
        {"params": [model.linear1.bias, model.inner.linear.weight]},
    ]
    optimizer = SIRFShampoo(model, params=param_groups, verbose_init=True)
    assert len(optimizer.param_groups) == 4
    assert optimizer.param_groups == [
        {"params": [model.linear1.weight], **defaults, "lam": 1234.0},
        {"params": [model.linear1.bias], **defaults},
        {"params": [model.inner.linear.weight], **defaults},
        {"params": [model.linear2.bias], **defaults, "lam": 1234.0},
    ]


def test_step_integration():
    """Check the optimizer is able to take a couple of steps without erroring."""
    manual_seed(0)
    batch_size = 6
    D_in, D_hidden, D_out = 5, 4, 3
    # use a nested network
    inner = Sequential(
        OrderedDict(
            {
                "linear": Linear(D_hidden, D_hidden, bias=False),
                "sigmoid": Sigmoid(),
            }
        )
    )
    model = Sequential(
        OrderedDict(
            {
                "linear1": Linear(D_in, D_hidden),
                "relu1": ReLU(),
                "inner": inner,
                "linear2": Linear(D_hidden, D_out),
            }
        )
    )
    loss_func = MSELoss()
    X, y = rand(batch_size, D_in), rand(batch_size, D_out)

    optimizer = SIRFShampoo(model, beta1=0.1, kappa=0.001)
    num_steps = 5
    losses = []
    for step in range(num_steps):
        optimizer.zero_grad()
        loss = loss_func(model(X), y)
        loss.backward()
        losses.append(loss.item())
        print(f"Step {step:03g}, Loss: {losses[-1]:.5f}")
        optimizer.step()

    assert losses[0] > losses[-1]
