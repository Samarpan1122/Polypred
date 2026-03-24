import re

with open("backend/app/services/training_service.py", "r") as f:
    code = f.read()

patch_graph = """    epochs = req.epochs
    bs = req.batch_size
    n = len(graphs_a_tr)
    progress.total_epochs = epochs

    # Use notebook DataLoaders
    import pandas as pd
    from app.models.notebook_dataloaders import PairDataset
    from torch_geometric.loader import DataLoader
    from torch_geometric.data import Batch
    
    # 1. Build DF for train and test PyG objects
    tr_df = pd.DataFrame({
        'Graph_A': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_a_tr],
        'Graph_B': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_b_tr],
        'log_r1': Y_tr[:, 0] if Y_tr.shape[1] > 0 else np.zeros(n),
        'log_r2': Y_tr[:, 1] if Y_tr.shape[1] > 1 else np.zeros(n)
    })
    
    # Check if testing data exists 
    n_te = len(graphs_a_te)
    te_df = pd.DataFrame({
        'Graph_A': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_a_te],
        'Graph_B': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_b_te],
        'log_r1': Y_te[:, 0] if Y_te.shape[1] > 0 else np.zeros(n_te),
        'log_r2': Y_te[:, 1] if Y_te.shape[1] > 1 else np.zeros(n_te)
    })

    def my_collate_fn(batch):
        ga = Batch.from_data_list([item[0] for item in batch])
        gb = Batch.from_data_list([item[1] for item in batch])
        tgt = torch.stack([item[2] for item in batch])
        return ga, gb, tgt

    train_loader = DataLoader(PairDataset(tr_df, list(range(len(tr_df)))), batch_size=bs, shuffle=True, collate_fn=my_collate_fn)

    for ep in range(epochs):
        model.train()
        ep_loss = 0.0
        nb = 0
        for batch_a, batch_b, tgt in train_loader:
            batch_a = batch_a.to(device)
            batch_b = batch_b.to(device)
            tgt = tgt.to(device)
            
            optimizer.zero_grad()
            try:
                pred = model(batch_a, batch_b)
                loss = criterion(pred, tgt[:, :pred.shape[1]])
                loss.backward()
                optimizer.step()
                ep_loss += loss.item()
                nb += 1
            except Exception as e:
                continue
"""

# Replace the specific block of generic training graph model
code = re.sub(
    r"    epochs = req\.epochs\n    bs = req\.batch_size\n    n = len\(graphs_a_tr\)\n    progress\.total_epochs = epochs\n\n    for ep in range\(epochs\):.+?            except Exception as e:\n                continue\n",
    patch_graph,
    code,
    flags=re.DOTALL
)

with open("backend/app/services/training_service.py", "w") as f:
    f.write(code)
