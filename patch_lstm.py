import re

with open("backend/app/services/training_service.py", "r") as f:
    code = f.read()

# I want to patch `_train_smiles_lstm`

patch_lstm = """    epochs = req.epochs
    bs = req.batch_size
    progress.total_epochs = epochs
    n = len(smiles_a_tr)

    import pandas as pd
    from app.models.notebook_dataloaders import PolyDataset, encode_smiles_lstm
    from app.models.benchmark_models import SMILES_VOCAB
    from torch.utils.data import DataLoader

    tr_df = pd.DataFrame({
        'SMILES_A': smiles_a_tr,
        'SMILES_B': smiles_b_tr,
        'log_r1': Y_tr[:, 0] if Y_tr.shape[1] > 0 else np.zeros(n),
        'log_r2': Y_tr[:, 1] if Y_tr.shape[1] > 1 else np.zeros(n)
    })
    
    n_te = len(smiles_a_te)
    te_df = pd.DataFrame({
        'SMILES_A': smiles_a_te,
        'SMILES_B': smiles_b_te,
        'log_r1': Y_te[:, 0] if Y_te.shape[1] > 0 else np.zeros(n_te),
        'log_r2': Y_te[:, 1] if Y_te.shape[1] > 1 else np.zeros(n_te)
    })

    train_loader = DataLoader(PolyDataset(tr_df, SMILES_VOCAB), batch_size=bs, shuffle=True)
    test_loader = DataLoader(PolyDataset(te_df, SMILES_VOCAB), batch_size=bs)

    for ep in range(epochs):
        model.train()
        ep_loss = 0.0
        nb = 0
        for ta, tb, yb in train_loader:
            ta = ta.to(device)
            tb = tb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad()
            pred = model(ta, tb)
            loss = criterion(pred, yb[:, :pred.shape[1]])
            loss.backward()
            optimizer.step()
            ep_loss += loss.item()
            nb += 1
"""

# We'll also patch the evaluation inside _train_smiles_lstm
patch_eval_lstm = """    # Evaluate
    model.eval()
    preds = []
    with torch.no_grad():
        for ta, tb, _ in test_loader:
            ta = ta.to(device)
            tb = tb.to(device)
            p = model(ta, tb).cpu().numpy()
            preds.append(p)
"""

# Match the training loop
code = re.sub(
    r"    epochs = req\.epochs\n    bs = req\.batch_size\n    progress\.total_epochs = epochs\n    n = len\(smiles_a_tr\)\n\n    for ep in range\(epochs\):.+?            nb \+= 1\n",
    patch_lstm,
    code,
    flags=re.DOTALL
)

# Match the eval loop
code = re.sub(
    r"    # Evaluate\n    model\.eval\(\)\n    preds = \[\]\n    with torch\.no_grad\(\):\n        for start in range\(0, len\(smiles_a_te\), bs\):\n            sa = smiles_a_te\[start:start \+ bs\]\n            sb = smiles_b_te\[start:start \+ bs\]\n            ta, tb = encode_batch\(sa, sb\)\n            p = model\(ta, tb\)\.cpu\(\)\.numpy\(\)\n            preds\.append\(p\)\n",
    patch_eval_lstm,
    code,
    flags=re.DOTALL
)

with open("backend/app/services/training_service.py", "w") as f:
    f.write(code)
